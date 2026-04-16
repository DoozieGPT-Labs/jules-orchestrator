#!/usr/bin/env python3
"""
Health Dashboard - Real-time health check endpoint with metrics
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
import subprocess


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    name: str
    status: str  # "pass", "fail", "warn"
    response_time_ms: float
    details: Dict[str, Any]
    timestamp: str


@dataclass
class SystemMetrics:
    """System-wide metrics snapshot"""

    cpu_percent: float
    memory_mb: float
    disk_percent: float
    uptime_seconds: float


class HealthDashboard:
    """
    Health dashboard for monitoring system health

    Provides:
    - Real-time health status
    - Circuit breaker states
    - Retry statistics
    - System metrics
    - Task execution stats
    """

    def __init__(self, repo: str, memory_file: str = "JULES_MEMORY.json"):
        self.repo = repo
        self.memory_file = memory_file
        self.dashboard_file = Path(".jules/health-dashboard.json")
        self.dashboard_file.parent.mkdir(parents=True, exist_ok=True)
        self._start_time = datetime.now()

    def generate_dashboard(self, memory: Optional[Dict] = None) -> Dict:
        """Generate full health dashboard"""
        dashboard = {
            "generated_at": datetime.now().isoformat(),
            "version": "4.0.0",
            "repo": self.repo,
            "status": "healthy",  # Will be updated based on checks
            "checks": {},
            "metrics": {},
            "circuit_breakers": {},
            "tasks": {},
        }

        # Run health checks
        dashboard["checks"] = self._run_health_checks()

        # Get system metrics
        dashboard["metrics"] = self._get_system_metrics()

        # Get circuit breaker states
        dashboard["circuit_breakers"] = self._get_circuit_breaker_states()

        # Get retry statistics
        dashboard["retry_stats"] = self._get_retry_stats()

        # Get task statistics
        if memory:
            dashboard["tasks"] = self._get_task_stats(memory)

        # Determine overall status
        if any(c["status"] == "fail" for c in dashboard["checks"].values()):
            dashboard["status"] = "unhealthy"
        elif any(c["status"] == "warn" for c in dashboard["checks"].values()):
            dashboard["status"] = "degraded"
        else:
            dashboard["status"] = "healthy"

        # Save dashboard
        self._save_dashboard(dashboard)

        return dashboard

    def _run_health_checks(self) -> Dict[str, Dict]:
        """Run all health checks"""
        checks = {}

        # Check GitHub API
        checks["github_api"] = self._check_github_api()

        # Check GitHub CLI
        checks["github_cli"] = self._check_github_cli()

        # Check memory file
        checks["memory_file"] = self._check_memory_file()

        # Check agent process
        checks["agent_process"] = self._check_agent_process()

        # Check disk space
        checks["disk_space"] = self._check_disk_space()

        return checks

    def _check_github_api(self) -> Dict:
        """Check GitHub API connectivity"""
        import time

        start = time.time()

        try:
            result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            elapsed = (time.time() - start) * 1000

            if result.returncode == 0:
                return {
                    "status": "pass",
                    "response_time_ms": round(elapsed, 2),
                    "details": {"user": result.stdout.strip()},
                }
            else:
                return {
                    "status": "fail",
                    "response_time_ms": round(elapsed, 2),
                    "details": {"error": result.stderr},
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "response_time_ms": 10000,
                "details": {"error": "Timeout after 10s"},
            }
        except Exception as e:
            return {
                "status": "fail",
                "response_time_ms": 0,
                "details": {"error": str(e)},
            }

    def _check_github_cli(self) -> Dict:
        """Check GitHub CLI availability"""
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                version = result.stdout.split("\n")[0]
                return {
                    "status": "pass",
                    "response_time_ms": 0,
                    "details": {"version": version},
                }
            else:
                return {
                    "status": "fail",
                    "response_time_ms": 0,
                    "details": {"error": "gh not available"},
                }
        except Exception as e:
            return {
                "status": "fail",
                "response_time_ms": 0,
                "details": {"error": str(e)},
            }

    def _check_memory_file(self) -> Dict:
        """Check memory file accessibility"""
        try:
            memory_path = Path(self.memory_file)
            if memory_path.exists():
                stat = memory_path.stat()
                return {
                    "status": "pass",
                    "response_time_ms": 0,
                    "details": {
                        "path": str(memory_path),
                        "size_bytes": stat.st_size,
                        "last_modified": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                    },
                }
            else:
                return {
                    "status": "warn",
                    "response_time_ms": 0,
                    "details": {"error": "Memory file not found"},
                }
        except Exception as e:
            return {
                "status": "fail",
                "response_time_ms": 0,
                "details": {"error": str(e)},
            }

    def _check_agent_process(self) -> Dict:
        """Check if agent process is running"""
        try:
            pid_file = Path(".jules/agent.pid")
            if pid_file.exists():
                with open(pid_file) as f:
                    data = json.load(f)
                    pid = data.get("pid")
                    status = data.get("status", "unknown")

                # Check if process exists
                try:
                    os.kill(pid, 0)
                    return {
                        "status": "pass",
                        "response_time_ms": 0,
                        "details": {
                            "pid": pid,
                            "status": status,
                            "running": True,
                        },
                    }
                except ProcessLookupError:
                    return {
                        "status": "warn",
                        "response_time_ms": 0,
                        "details": {
                            "pid": pid,
                            "status": status,
                            "running": False,
                        },
                    }
            else:
                return {
                    "status": "warn",
                    "response_time_ms": 0,
                    "details": {"error": "PID file not found"},
                }
        except Exception as e:
            return {
                "status": "fail",
                "response_time_ms": 0,
                "details": {"error": str(e)},
            }

    def _check_disk_space(self) -> Dict:
        """Check disk space availability"""
        try:
            stat = os.statvfs(".")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
            used_percent = ((total_gb - free_gb) / total_gb) * 100

            status = "pass"
            if used_percent > 90:
                status = "fail"
            elif used_percent > 80:
                status = "warn"

            return {
                "status": status,
                "response_time_ms": 0,
                "details": {
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "used_percent": round(used_percent, 1),
                },
            }
        except Exception as e:
            return {
                "status": "fail",
                "response_time_ms": 0,
                "details": {"error": str(e)},
            }

    def _get_system_metrics(self) -> Dict:
        """Get system resource metrics"""
        metrics = {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
        }

        try:
            import psutil

            # CPU
            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)

            # Memory
            mem = psutil.virtual_memory()
            metrics["memory_mb"] = round(mem.used / 1024 / 1024, 2)
            metrics["memory_percent"] = mem.percent

            # Disk
            disk = psutil.disk_usage(".")
            metrics["disk_percent"] = disk.percent

        except ImportError:
            metrics["note"] = "psutil not available for detailed metrics"

        return metrics

    def _get_circuit_breaker_states(self) -> Dict:
        """Get all circuit breaker states"""
        try:
            from circuit_breaker import get_all_circuit_states

            return get_all_circuit_states()
        except Exception as e:
            return {"error": str(e)}

    def _get_retry_stats(self) -> Dict:
        """Get retry statistics"""
        # This would be populated by retry manager
        return {
            "note": "Retry stats available via RetryManager.get_stats()",
        }

    def _get_task_stats(self, memory: Dict) -> Dict:
        """Get task execution statistics"""
        tasks = memory.get("tasks", [])

        if not tasks:
            return {"total": 0}

        stats = {
            "total": len(tasks),
            "by_status": {},
            "completed": 0,
            "failed": 0,
            "blocked": 0,
            "progress_percent": 0,
        }

        for task in tasks:
            status = task.get("status", "unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            if status == "complete":
                stats["completed"] += 1
            elif status == "failed":
                stats["failed"] += 1
            elif status == "blocked":
                stats["blocked"] += 1

        stats["progress_percent"] = round((stats["completed"] / len(tasks)) * 100, 1)

        return stats

    def _save_dashboard(self, dashboard: Dict):
        """Save dashboard to file"""
        try:
            with open(self.dashboard_file, "w") as f:
                json.dump(dashboard, f, indent=2)
        except Exception as e:
            pass

    def get_dashboard(self) -> Optional[Dict]:
        """Get latest dashboard from file"""
        try:
            if self.dashboard_file.exists():
                with open(self.dashboard_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def generate_html_report(self, dashboard: Optional[Dict] = None) -> str:
        """Generate HTML dashboard report"""
        if dashboard is None:
            dashboard = self.get_dashboard()

        if not dashboard:
            return "<h1>No dashboard data available</h1>"

        status_color = {
            "healthy": "#4CAF50",
            "degraded": "#FF9800",
            "unhealthy": "#F44336",
        }.get(dashboard["status"], "#9E9E9E")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Jules Orchestrator Health Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .header {{ background: {status_color}; color: white; padding: 20px; border-radius: 5px; }}
        .section {{ background: white; margin: 20px 0; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .check {{ display: flex; align-items: center; margin: 10px 0; padding: 10px; border-left: 4px solid; }}
        .check.pass {{ border-color: #4CAF50; background: #E8F5E9; }}
        .check.warn {{ border-color: #FF9800; background: #FFF3E0; }}
        .check.fail {{ border-color: #F44336; background: #FFEBEE; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #E3F2FD; border-radius: 5px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #1976D2; }}
        .metric-label {{ font-size: 12px; color: #666; }}
        pre {{ background: #f5f5f5; padding: 10px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Jules Orchestrator Health Dashboard</h1>
        <p>Status: <strong>{dashboard["status"].upper()}</strong> | Repo: {dashboard["repo"]} | Version: {dashboard["version"]}</p>
        <p>Generated: {dashboard["generated_at"]}</p>
    </div>
    
    <div class="section">
        <h2>Health Checks</h2>
"""

        for name, check in dashboard.get("checks", {}).items():
            status = check.get("status", "unknown")
            details = check.get("details", {})
            html += f"""
        <div class="check {status}">
            <strong>{name.upper()}</strong>: {status.upper()}
            <span style="margin-left: 20px; color: #666;">{details}</span>
        </div>
"""

        html += """
    </div>
    
    <div class="section">
        <h2>Task Statistics</h2>
"""

        tasks = dashboard.get("tasks", {})
        html += f"""
        <div class="metric">
            <div class="metric-value">{tasks.get("total", 0)}</div>
            <div class="metric-label">Total Tasks</div>
        </div>
        <div class="metric">
            <div class="metric-value">{tasks.get("completed", 0)}</div>
            <div class="metric-label">Completed</div>
        </div>
        <div class="metric">
            <div class="metric-value">{tasks.get("progress_percent", 0)}%</div>
            <div class="metric-label">Progress</div>
        </div>
"""

        html += """
    </div>
    
    <div class="section">
        <h2>Raw Data</h2>
        <pre>
"""
        html += json.dumps(dashboard, indent=2)
        html += """
        </pre>
    </div>
</body>
</html>
"""

        return html


def generate_health_check_endpoint(repo: str, memory: Optional[Dict] = None) -> Dict:
    """Generate health check endpoint data"""
    dashboard = HealthDashboard(repo)
    return dashboard.generate_dashboard(memory)


if __name__ == "__main__":
    # Test
    dashboard = HealthDashboard("test/repo")
    data = dashboard.generate_dashboard()

    print("Health Dashboard Generated:")
    print(json.dumps(data, indent=2))

    # Generate HTML
    html = dashboard.generate_html_report(data)
    with open("health-dashboard.html", "w") as f:
        f.write(html)
    print("\n✅ HTML report saved to health-dashboard.html")
