#!/usr/bin/env python3
"""
Process Manager - PID file, health checks, and graceful shutdown
"""

import os
import sys
import signal
import atexit
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
import psutil


class ProcessManager:
    """
    Manages background agent process with:
    - PID file tracking
    - Health check endpoint
    - Graceful shutdown handling
    - Single instance enforcement
    """

    def __init__(self, pid_file: str = ".jules/agent.pid", repo: Optional[str] = None):
        self.pid_file = Path(pid_file)
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.repo = repo
        self.running = False
        self.start_time = None
        self._register_signal_handlers()

    def _register_signal_handlers(self):
        """Register handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGHUP, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        sig_name = signal.Signals(signum).name
        print(f"\n[{sig_name}] Shutting down gracefully...")
        self.running = False

    def is_running(self) -> bool:
        """Check if another agent instance is running"""
        if not self.pid_file.exists():
            return False

        try:
            with open(self.pid_file, "r") as f:
                data = json.load(f)
                pid = data.get("pid")

            if not pid:
                return False

            # Check if process exists
            try:
                process = psutil.Process(pid)
                # Verify it's our agent
                cmdline = " ".join(process.cmdline())
                if "background_agent" in cmdline or "jules-agent" in cmdline:
                    return True
                else:
                    # PID reused by different process
                    return False
            except psutil.NoSuchProcess:
                # Stale PID file
                return False

        except (json.JSONDecodeError, FileNotFoundError):
            return False

    def acquire(self) -> bool:
        """Acquire exclusive lock - returns True if acquired"""
        if self.is_running():
            print("❌ Another agent instance is already running")
            print(f"   PID file: {self.pid_file}")
            print(f"   Run '/jules-status' to check status")
            return False

        self.start_time = datetime.now()
        self.running = True

        # Write PID file
        data = {
            "pid": os.getpid(),
            "started_at": self.start_time.isoformat(),
            "repo": self.repo,
            "status": "running",
        }

        with open(self.pid_file, "w") as f:
            json.dump(data, f, indent=2)

        # Register cleanup on exit
        atexit.register(self.release)

        print(f"✅ Agent started (PID: {data['pid']})")
        return True

    def release(self):
        """Release PID file and cleanup"""
        try:
            self.running = False
            if self.pid_file.exists():
                self.pid_file.unlink()
                print("✅ PID file cleaned up")
        except Exception:
            pass

    def update_status(self, status: str, memory: Optional[Dict] = None):
        """Update status in PID file"""
        try:
            with open(self.pid_file, "r") as f:
                data = json.load(f)

            data["status"] = status
            data["last_update"] = datetime.now().isoformat()

            if memory:
                tasks = memory.get("tasks", [])
                completed = len([t for t in tasks if t["status"] == "complete"])
                data["progress"] = f"{completed}/{len(tasks)}"

            with open(self.pid_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception:
            pass

    def get_status(self) -> Optional[Dict]:
        """Get current agent status from PID file"""
        if not self.pid_file.exists():
            return None

        try:
            with open(self.pid_file, "r") as f:
                data = json.load(f)

            pid = data.get("pid")
            if pid:
                try:
                    process = psutil.Process(pid)
                    data["process_status"] = process.status()
                    data["cpu_percent"] = process.cpu_percent()
                    data["memory_mb"] = process.memory_info().rss / 1024 / 1024
                except psutil.NoSuchProcess:
                    data["process_status"] = "not_running"

            return data

        except Exception:
            return None

    def kill(self) -> bool:
        """Kill running agent"""
        status = self.get_status()
        if not status:
            print("No agent running")
            return False

        pid = status.get("pid")
        if not pid:
            print("Invalid PID file")
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to process {pid}")

            # Wait for graceful shutdown
            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)  # Check if still exists
                except ProcessLookupError:
                    print("✅ Agent stopped")
                    return True

            # Force kill if still running
            print("Force killing...")
            os.kill(pid, signal.SIGKILL)
            return True

        except ProcessLookupError:
            print("Process not found")
            self.release()
            return False
        except Exception as e:
            print(f"Error killing process: {e}")
            return False


class HealthChecker:
    """
    Health check endpoint for monitoring
    """

    def __init__(self, health_file: str = ".jules/health.json"):
        self.health_file = Path(health_file)
        self.health_file.parent.mkdir(parents=True, exist_ok=True)
        self.checks = {}
        self.last_healthy = None

    def register_check(self, name: str, check_func):
        """Register a health check function"""
        self.checks[name] = check_func

    def run_checks(self) -> Dict:
        """Run all health checks"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "healthy": True,
            "checks": {},
        }

        for name, check_func in self.checks.items():
            try:
                result = check_func()
                results["checks"][name] = {
                    "status": "pass" if result else "fail",
                    "healthy": result,
                }
                if not result:
                    results["healthy"] = False
            except Exception as e:
                results["checks"][name] = {
                    "status": "error",
                    "error": str(e),
                    "healthy": False,
                }
                results["healthy"] = False

        self.last_healthy = results["healthy"]
        self._save(results)
        return results

    def _save(self, results: Dict):
        """Save health check results"""
        with open(self.health_file, "w") as f:
            json.dump(results, f, indent=2)

    def get_last_check(self) -> Optional[Dict]:
        """Get last health check results"""
        if not self.health_file.exists():
            return None

        try:
            with open(self.health_file, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def is_healthy(self) -> bool:
        """Quick health check"""
        if self.last_healthy is not None:
            return self.last_healthy

        results = self.get_last_check()
        return results.get("healthy", False) if results else False


def check_github_api() -> bool:
    """Check GitHub API connectivity"""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_git_repo() -> bool:
    """Check git repository status"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


if __name__ == "__main__":
    # Test
    import subprocess

    manager = ProcessManager()

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status = manager.get_status()
        if status:
            print(f"Agent status: {json.dumps(status, indent=2)}")
        else:
            print("No agent running")
    elif len(sys.argv) > 1 and sys.argv[1] == "kill":
        manager.kill()
    else:
        if manager.acquire():
            print("Running for 5 seconds...")
            time.sleep(5)
            manager.release()
