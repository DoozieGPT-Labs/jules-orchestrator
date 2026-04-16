#!/usr/bin/env python3
"""
Resume Logic - Reconstruct state from memory and continue
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set
import os


class JulesResumeLogic:
    """Handle resuming orchestration from memory file"""

    def __init__(self, repo: str, memory_file: str = "JULES_MEMORY.json"):
        self.repo = repo
        self.memory_file = memory_file

    def resume(self) -> Dict:
        """
        Resume orchestration from memory
        Returns status report
        """
        memory = self.load_memory()

        if not memory:
            return {
                "success": False,
                "error": "No memory file found. Run /plan-work first.",
                "status": "no_memory",
            }

        # Check current status
        current_status = memory.get("status", "unknown")

        if current_status == "complete":
            return {
                "success": True,
                "status": "complete",
                "message": "All tasks already complete!",
                "final_pr": memory.get("final_pr", "N/A"),
                "tasks": memory.get("tasks", []),
            }

        if current_status == "failed":
            return {
                "success": False,
                "status": "failed",
                "message": "Previous execution failed. Check memory for details.",
                "tasks": memory.get("tasks", []),
            }

        # Reconstruct state
        tasks = memory.get("tasks", [])

        completed = [t for t in tasks if t["status"] == "complete"]
        failed = [t for t in tasks if t["status"] in ["failed", "blocked"]]
        pending = [
            t
            for t in tasks
            if t["status"] in ["pending", "issue_created", "jules_triggered"]
        ]
        executing = [
            t
            for t in tasks
            if t["status"] in ["pr_opened", "validating", "approved", "merging"]
        ]

        # Check if background agent running
        agent_running = self.is_agent_running()

        # Check for orphaned PRs (PRs opened but task not tracking)
        orphaned = self.find_orphaned_prs(tasks)

        # Check for completed PRs not marked complete
        completed_prs = self.find_completed_prs(tasks)

        return {
            "success": True,
            "status": current_status,
            "agent_running": agent_running,
            "summary": {
                "total": len(tasks),
                "completed": len(completed),
                "failed": len(failed),
                "executing": len(executing),
                "pending": len(pending),
                "progress": f"{len(completed)}/{len(tasks)} ({len(completed) / len(tasks) * 100:.0f}%)"
                if tasks
                else "0%",
            },
            "tasks": {
                "completed": completed,
                "failed": failed,
                "executing": executing,
                "pending": pending,
            },
            "orphaned_prs": orphaned,
            "completed_prs": completed_prs,
            "recommendations": self.generate_recommendations(
                memory, agent_running, failed, orphaned
            ),
        }

    def load_memory(self) -> Optional[Dict]:
        """Load memory file"""
        try:
            if Path(self.memory_file).exists():
                with open(self.memory_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading memory: {e}")
        return None

    def is_agent_running(self) -> bool:
        """Check if background agent process is running"""
        try:
            # Check for Python process with background_agent.py
            result = subprocess.run(
                ["pgrep", "-f", "background_agent.py"], capture_output=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def find_orphaned_prs(self, tasks: List[Dict]) -> List[Dict]:
        """Find PRs that exist but aren't tracked in tasks"""
        orphaned = []
        task_prs = {t.get("pr_id") for t in tasks if t.get("pr_id")}

        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "-R",
                    self.repo,
                    "--state",
                    "open",
                    "--json",
                    "number,title",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            prs = json.loads(result.stdout)

            for pr in prs:
                if pr["number"] not in task_prs and "[AUTO]" in pr.get("title", ""):
                    orphaned.append(
                        {
                            "number": pr["number"],
                            "title": pr["title"],
                            "action": "Link to task or close manually",
                        }
                    )
        except Exception:
            pass

        return orphaned

    def find_completed_prs(self, tasks: List[Dict]) -> List[Dict]:
        """Find PRs that are merged but task not marked complete"""
        completed = []

        for task in tasks:
            if task["status"] not in ["pr_opened", "validating", "approved", "merging"]:
                continue

            pr_info = self.get_pr_info(task.get("pr_id"))
            if pr_info and pr_info.get("merged"):
                completed.append(
                    {
                        "task_id": task["id"],
                        "pr_number": pr_info["number"],
                        "action": "Update task status to complete",
                    }
                )

        return completed

    def get_pr_info(self, pr_number: Optional[int]) -> Optional[Dict]:
        """Get PR info"""
        if not pr_number:
            return None

        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "-R",
                    self.repo,
                    "--json",
                    "number,title,state,merged",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except Exception:
            return None

    def generate_recommendations(
        self,
        memory: Dict,
        agent_running: bool,
        failed: List[Dict],
        orphaned: List[Dict],
    ) -> List[str]:
        """Generate recommendations based on state"""
        recommendations = []

        if not agent_running:
            recommendations.append("Start background agent: /jules-start")

        if failed:
            recommendations.append(f"Review {len(failed)} failed tasks in memory file")
            recommendations.append("Consider: /jules-retry-failed")

        if orphaned:
            recommendations.append(f"Review {len(orphaned)} orphaned PRs")

        if memory.get("status") == "executing" and agent_running:
            recommendations.append("Check status: /jules-status")

        return recommendations

    def start_background_agent(self) -> bool:
        """Start background agent process"""
        try:
            # Start agent in background
            cmd = [
                "nohup",
                "python3",
                "background_agent.py",
                "--repo",
                self.repo,
                "--memory",
                self.memory_file,
                ">",
                "jules-agent.log",
                "2>&1",
                "&",
            ]
            subprocess.run(" ".join(cmd), shell=True, check=True)
            return True
        except Exception as e:
            print(f"Error starting agent: {e}")
            return False

    def rebuild_dependency_graph(self, tasks: List[Dict]) -> Dict:
        """Rebuild dependency graph from tasks"""
        graph = {}
        for task in tasks:
            graph[task["id"]] = {
                "task": task,
                "dependencies": task.get("dependencies", []),
                "dependents": [],
            }

        # Find dependents
        for task_id, data in graph.items():
            for dep in data["dependencies"]:
                if dep in graph:
                    graph[dep]["dependents"].append(task_id)

        return graph

    def get_ready_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Get tasks ready to execute (all deps complete)"""
        completed_ids = {t["id"] for t in tasks if t["status"] == "complete"}

        ready = []
        for task in tasks:
            if task["status"] != "pending":
                continue
            deps = task.get("dependencies", [])
            if all(d in completed_ids for d in deps):
                ready.append(task)

        return ready


def resume_orchestration(repo: str, memory_file: str = "JULES_MEMORY.json") -> Dict:
    """
    Main entry point for resume command
    """
    logic = JulesResumeLogic(repo, memory_file)
    return logic.resume()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python resume_logic.py <repo> [memory_file]")
        sys.exit(1)

    repo = sys.argv[1]
    memory_file = sys.argv[2] if len(sys.argv) > 2 else "JULES_MEMORY.json"

    result = resume_orchestration(repo, memory_file)
    print(json.dumps(result, indent=2))
