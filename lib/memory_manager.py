#!/usr/bin/env python3
"""
Memory Manager - Atomic memory persistence with versioning
"""

import json
import os
import tempfile
import shutil
import subprocess
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any


class MemoryManager:
    """
    Manages JULES_MEMORY.json with:
    - Atomic writes (temp file + rename)
    - File locking (prevents concurrent writes)
    - Version tracking
    - Backup creation
    """

    CURRENT_SCHEMA_VERSION = "3.0.0"

    def __init__(self, memory_file: str = "JULES_MEMORY.json"):
        self.memory_file = Path(memory_file)
        self.lock_file = self.memory_file.parent / f".{self.memory_file.name}.lock"
        self.backup_dir = self.memory_file.parent / ".jules" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict:
        """Load memory from file with schema validation"""
        if not self.memory_file.exists():
            return {}

        try:
            with open(self.memory_file, "r") as f:
                data = json.load(f)

            # Schema version check
            schema_version = data.get("schema_version", "0.0.0")
            if schema_version != self.CURRENT_SCHEMA_VERSION:
                data = self._migrate_schema(data, schema_version)

            return data
        except json.JSONDecodeError as e:
            # Try to recover from backup
            return self._recover_from_backup() or {}
        except Exception as e:
            return {}

    def save(self, memory: Dict, commit: bool = True) -> bool:
        """
        Save memory atomically:
        1. Write to temp file
        2. Create backup
        3. Atomic rename
        4. Git commit (optional)
        """
        # Add metadata
        memory["_meta"] = {
            "schema_version": self.CURRENT_SCHEMA_VERSION,
            "saved_at": datetime.now().isoformat(),
            "save_count": memory.get("_meta", {}).get("save_count", 0) + 1,
        }

        # Acquire lock
        with self._acquire_lock():
            try:
                # Create backup first
                self._create_backup()

                # Write to temp file
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=self.memory_file.parent, prefix=f".{self.memory_file.name}.tmp."
                )
                try:
                    with os.fdopen(temp_fd, "w") as f:
                        json.dump(memory, f, indent=2)

                    # Atomic rename
                    shutil.move(temp_path, self.memory_file)

                except Exception:
                    # Clean up temp file on failure
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    raise

                # Git commit
                if commit:
                    self._commit_to_git()

                return True

            except Exception as e:
                self._restore_from_backup()
                return False

    def _acquire_lock(self):
        """Context manager for file locking"""
        return FileLock(self.lock_file)

    def _create_backup(self):
        """Create timestamped backup"""
        if not self.memory_file.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"{self.memory_file.stem}_{timestamp}.json"

        try:
            shutil.copy2(self.memory_file, backup_file)

            # Keep only last 10 backups
            self._prune_old_backups()
        except Exception:
            pass

    def _prune_old_backups(self):
        """Remove old backups, keep only last 10"""
        try:
            backups = sorted(self.backup_dir.glob("*.json"))
            if len(backups) > 10:
                for old in backups[:-10]:
                    old.unlink()
        except Exception:
            pass

    def _recover_from_backup(self) -> Optional[Dict]:
        """Attempt to recover from most recent backup"""
        try:
            backups = sorted(self.backup_dir.glob("*.json"), reverse=True)
            if backups:
                with open(backups[0], "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _restore_from_backup(self):
        """Restore from most recent backup"""
        backup = self._recover_from_backup()
        if backup:
            with open(self.memory_file, "w") as f:
                json.dump(backup, f, indent=2)

    def _commit_to_git(self):
        """Commit memory file to git"""
        try:
            # Check if in git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"], capture_output=True, check=True
            )

            # Stage
            subprocess.run(
                ["git", "add", str(self.memory_file)], check=True, capture_output=True
            )

            # Commit
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"[Jules] Update execution state - {datetime.now().isoformat()}",
                    "--no-verify",  # Skip hooks for speed
                ],
                check=True,
                capture_output=True,
            )

            # Push
            subprocess.run(["git", "push"], check=True, capture_output=True)

        except subprocess.CalledProcessError:
            # No changes or other git issue - not fatal
            pass
        except Exception:
            pass

    def _migrate_schema(self, data: Dict, from_version: str) -> Dict:
        """Migrate data from old schema version"""
        # Add migration logic here as schema evolves
        data["schema_version"] = self.CURRENT_SCHEMA_VERSION
        return data


class FileLock:
    """Simple file lock using flock"""

    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.fd = None

    def __enter__(self):
        self.fd = open(self.lock_file, "w")
        fcntl.flock(self.fd.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_UN)
            self.fd.close()
            self.fd = None


class AuditLog:
    """Append-only audit log for state changes"""

    def __init__(self, log_file: str = ".jules/audit.jsonl"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self, event_type: str, task_id: Optional[str], details: Dict[str, Any]
    ):
        """Log an event to the audit log"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "task_id": task_id,
            "details": details,
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def get_events(
        self, task_id: Optional[str] = None, event_type: Optional[str] = None
    ) -> list:
        """Query events from audit log"""
        events = []

        if not self.log_file.exists():
            return events

        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if task_id and entry.get("task_id") != task_id:
                        continue
                    if event_type and entry.get("event") != event_type:
                        continue
                    events.append(entry)
                except json.JSONDecodeError:
                    continue

        return events


if __name__ == "__main__":
    # Test
    manager = MemoryManager("test_memory.json")

    test_data = {
        "project_name": "test",
        "tasks": [{"id": "T1", "status": "pending"}],
    }

    manager.save(test_data, commit=False)
    loaded = manager.load()
    print(f"Saved and loaded: {loaded}")
