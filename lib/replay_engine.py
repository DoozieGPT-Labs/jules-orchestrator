#!/usr/bin/env python3
"""
Task Replay Engine - Deterministic re-run and execution snapshotting
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib
import shutil


class ReplayEngine:
    """
    Store and replay task executions
    Enables debugging, iteration, and determinism
    """

    def __init__(self, repo: str, replay_dir: str = ".jules/replays"):
        self.repo = repo
        self.replay_dir = Path(replay_dir)
        self.replay_dir.mkdir(parents=True, exist_ok=True)

    def capture_snapshot(
        self, task: Dict, skills: List[str], jules_prompt: str, repo_state: str
    ) -> Dict:
        """
        Capture full execution state for replay
        """
        snapshot = {
            "version": "1.0.0",
            "task_id": task.get("id"),
            "task": task,
            "timestamp": datetime.now().isoformat(),
            "repo_state": repo_state,
            "repo_commit": self._get_current_commit(),
            "skills_used": skills,
            "jules_prompt": jules_prompt,
            "files_expected": task.get("files_expected", []),
            "acceptance_criteria": task.get("acceptance_criteria", []),
            "test_cases": task.get("test_cases", []),
            "dependencies": task.get("dependencies", []),
            "snapshot_hash": self._calculate_hash(task, skills, jules_prompt),
            "execution_context": {
                "working_dir": str(Path.cwd()),
                "git_branch": self._get_current_branch(),
                "git_remote": self._get_remote_url(),
            },
        }

        # Save to replay log
        self._save_snapshot(snapshot)

        return snapshot

    def _calculate_hash(self, task: Dict, skills: List[str], prompt: str) -> str:
        """Calculate deterministic hash for this execution"""
        content = json.dumps(
            {
                "task": task.get("id"),
                "files": sorted(task.get("files_expected", [])),
                "criteria": task.get("acceptance_criteria", []),
                "skills": sorted(skills),
                "prompt": prompt[:500],  # First 500 chars
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _save_snapshot(self, snapshot: Dict):
        """Save snapshot to replay directory"""
        task_id = snapshot["task_id"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task_id}_{timestamp}.json"

        filepath = self.replay_dir / filename
        with open(filepath, "w") as f:
            json.dump(snapshot, f, indent=2)

        # Also update index
        index_file = self.replay_dir / "index.json"
        index = []
        if index_file.exists():
            with open(index_file, "r") as f:
                index = json.load(f)

        index.append(
            {
                "task_id": task_id,
                "timestamp": snapshot["timestamp"],
                "file": filename,
                "hash": snapshot["snapshot_hash"],
                "repo_commit": snapshot["repo_commit"],
            }
        )

        with open(index_file, "w") as f:
            json.dump(index, f, indent=2)

    def replay_task(
        self, task_id: str, snapshot_file: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Replay a task from snapshot
        Returns the snapshot to re-execute
        """
        if snapshot_file:
            # Specific snapshot
            filepath = self.replay_dir / snapshot_file
            if filepath.exists():
                with open(filepath, "r") as f:
                    return json.load(f)
            return None

        # Get latest for task
        index_file = self.replay_dir / "index.json"
        if not index_file.exists():
            return None

        with open(index_file, "r") as f:
            index = json.load(f)

        # Find latest for task
        task_snapshots = [s for s in index if s["task_id"] == task_id]
        if not task_snapshots:
            return None

        # Sort by timestamp, get latest
        latest = sorted(task_snapshots, key=lambda x: x["timestamp"], reverse=True)[0]

        # Load full snapshot
        filepath = self.replay_dir / latest["file"]
        with open(filepath, "r") as f:
            return json.load(f)

    def list_replays(self, task_id: Optional[str] = None) -> List[Dict]:
        """List available replays"""
        index_file = self.replay_dir / "index.json"
        if not index_file.exists():
            return []

        with open(index_file, "r") as f:
            index = json.load(f)

        if task_id:
            return [s for s in index if s["task_id"] == task_id]

        return index

    def compare_replays(self, snapshot1: str, snapshot2: str) -> Dict:
        """Compare two replay snapshots"""
        s1 = self._load_snapshot_file(snapshot1)
        s2 = self._load_snapshot_file(snapshot2)

        if not s1 or not s2:
            return {"error": "Could not load snapshots"}

        return {
            "task_id": s1.get("task_id"),
            "snapshots": [snapshot1, snapshot2],
            "differences": {
                "skills": {
                    "before": s1.get("skills_used", []),
                    "after": s2.get("skills_used", []),
                    "changed": s1.get("skills_used") != s2.get("skills_used"),
                },
                "files_expected": {
                    "before": s1.get("files_expected", []),
                    "after": s2.get("files_expected", []),
                    "changed": s1.get("files_expected") != s2.get("files_expected"),
                },
                "prompt_changed": s1.get("jules_prompt") != s2.get("jules_prompt"),
                "time_delta": self._calculate_time_delta(
                    s1.get("timestamp"), s2.get("timestamp")
                ),
            },
        }

    def _load_snapshot_file(self, filename: str) -> Optional[Dict]:
        """Load a specific snapshot file"""
        filepath = self.replay_dir / filename
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
        return None

    def _calculate_time_delta(self, ts1: str, ts2: str) -> str:
        """Calculate time difference between snapshots"""
        try:
            from datetime import datetime

            t1 = datetime.fromisoformat(ts1)
            t2 = datetime.fromisoformat(ts2)
            delta = abs((t2 - t1).total_seconds())

            if delta < 60:
                return f"{int(delta)}s"
            elif delta < 3600:
                return f"{int(delta / 60)}m"
            else:
                return f"{int(delta / 3600)}h"
        except:
            return "unknown"

    def _get_current_commit(self) -> str:
        """Get current git commit"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except:
            return "unknown"

    def _get_current_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except:
            return "unknown"

    def _get_remote_url(self) -> str:
        """Get git remote URL"""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except:
            return "unknown"

    def generate_replay_plan(self, task_id: str) -> Dict:
        """Generate a replay plan for debugging"""
        snapshot = self.replay_task(task_id)
        if not snapshot:
            return {"error": f"No replay found for {task_id}"}

        return {
            "task_id": task_id,
            "original_timestamp": snapshot["timestamp"],
            "replay_steps": [
                {
                    "step": 1,
                    "action": "checkout_repo",
                    "commit": snapshot["repo_commit"],
                    "description": f"Checkout repo at commit {snapshot['repo_commit'][:8]}",
                },
                {
                    "step": 2,
                    "action": "install_skills",
                    "skills": snapshot["skills_used"],
                    "description": "Install same skills as original execution",
                },
                {
                    "step": 3,
                    "action": "generate_prompt",
                    "description": "Generate identical Jules prompt",
                },
                {
                    "step": 4,
                    "action": "execute_jules",
                    "prompt_hash": snapshot["snapshot_hash"],
                    "description": "Execute Jules with identical context",
                },
                {
                    "step": 5,
                    "action": "compare_output",
                    "description": "Compare output with original execution",
                },
            ],
            "can_replay": True,
            "snapshot": snapshot,
        }


class ExecutionMetrics:
    """
    Track execution metrics for ROI analysis
    """

    def __init__(self, metrics_file: str = ".jules/metrics.json"):
        self.metrics_file = Path(metrics_file)
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_metrics()

    def _load_metrics(self) -> Dict:
        """Load existing metrics"""
        if self.metrics_file.exists():
            with open(self.metrics_file, "r") as f:
                return json.load(f)
        return {
            "tasks": [],
            "summary": {"total_tasks": 0, "completed": 0, "failed": 0, "retried": 0},
        }

    def record_task_start(self, task_id: str):
        """Record task start"""
        self.data["tasks"].append(
            {
                "task_id": task_id,
                "start_time": datetime.now().isoformat(),
                "status": "started",
            }
        )
        self._save()

    def record_task_complete(
        self,
        task_id: str,
        success: bool,
        retries: int = 0,
        pr_number: Optional[int] = None,
    ):
        """Record task completion"""
        for task in self.data["tasks"]:
            if task["task_id"] == task_id and task.get("status") == "started":
                task["end_time"] = datetime.now().isoformat()
                task["status"] = "completed" if success else "failed"
                task["success"] = success
                task["retries"] = retries
                task["pr_number"] = pr_number

                # Calculate duration
                try:
                    start = datetime.fromisoformat(task["start_time"])
                    end = datetime.fromisoformat(task["end_time"])
                    task["duration_seconds"] = (end - start).total_seconds()
                except:
                    task["duration_seconds"] = 0

                break

        self._update_summary()
        self._save()

    def _update_summary(self):
        """Update summary statistics"""
        completed = [t for t in self.data["tasks"] if t.get("status") == "completed"]
        failed = [t for t in self.data["tasks"] if t.get("status") == "failed"]
        retried = [t for t in self.data["tasks"] if t.get("retries", 0) > 0]

        self.data["summary"] = {
            "total_tasks": len(self.data["tasks"]),
            "completed": len(completed),
            "failed": len(failed),
            "retried": len(retried),
            "success_rate": len(completed) / len(self.data["tasks"])
            if self.data["tasks"]
            else 0,
            "avg_retries": sum(t.get("retries", 0) for t in self.data["tasks"])
            / len(self.data["tasks"])
            if self.data["tasks"]
            else 0,
        }

    def _save(self):
        """Save metrics"""
        with open(self.metrics_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def get_report(self) -> Dict:
        """Generate metrics report"""
        return {
            "summary": self.data["summary"],
            "recent_tasks": self.data["tasks"][-10:],
            "weekly_stats": self._calculate_weekly_stats(),
        }

    def _calculate_weekly_stats(self) -> Dict:
        """Calculate weekly statistics"""
        # Implementation for weekly stats
        return {}


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python replay_engine.py <command> [args]")
        print("Commands:")
        print("  list [task_id]     - List available replays")
        print("  replay <task_id>   - Replay a task")
        print("  compare <s1> <s2>  - Compare two snapshots")
        sys.exit(1)

    command = sys.argv[1]
    engine = ReplayEngine(".")

    if command == "list":
        task_id = sys.argv[2] if len(sys.argv) > 2 else None
        replays = engine.list_replays(task_id)
        for r in replays:
            print(f"{r['task_id']}: {r['timestamp']} ({r['file']})")

    elif command == "replay":
        if len(sys.argv) < 3:
            print("Usage: replay <task_id>")
            sys.exit(1)

        task_id = sys.argv[2]
        plan = engine.generate_replay_plan(task_id)
        print(json.dumps(plan, indent=2))

    elif command == "compare":
        if len(sys.argv) < 4:
            print("Usage: compare <snapshot1> <snapshot2>")
            sys.exit(1)

        result = engine.compare_replays(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
