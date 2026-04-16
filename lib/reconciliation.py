#!/usr/bin/env python3
"""
Reconciliation Engine - Detect and recover orphaned/orphaned resources
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OrphanedResource:
    """Represents an orphaned resource"""

    resource_type: str  # 'issue', 'pr', 'branch'
    resource_id: str
    resource_number: Optional[int]
    detected_at: str
    reason: str
    suggested_action: str
    auto_fixable: bool


class ReconciliationEngine:
    """
    Detects and reconciles orphaned resources:
    - PRs that exist but aren't tracked in tasks
    - Issues created but task lost tracking
    - Branches left behind after merge
    - Tasks stuck in transient states
    """

    def __init__(self, github_client, memory_manager, audit_log):
        self.github = github_client
        self.memory = memory_manager
        self.audit = audit_log
        self.logger = logging.getLogger("reconciliation-engine")
        self.orphaned: List[OrphanedResource] = []

    def run_full_reconciliation(self, memory: Dict) -> Dict:
        """
        Run full reconciliation scan

        Returns report of orphaned resources and actions taken
        """
        self.orphaned = []

        report = {
            "started_at": datetime.now().isoformat(),
            "orphaned_found": [],
            "actions_taken": [],
            "errors": [],
        }

        try:
            # Check for orphaned PRs
            orphaned_prs = self._find_orphaned_prs(memory)
            self.orphaned.extend(orphaned_prs)

            # Check for orphaned issues
            orphaned_issues = self._find_orphaned_issues(memory)
            self.orphaned.extend(orphaned_issues)

            # Check for stuck tasks
            stuck_tasks = self._find_stuck_tasks(memory)
            for task_id, reason in stuck_tasks:
                self._attempt_stuck_recovery(memory, task_id, reason)

            # Check for completed PRs not marked complete
            completed_missed = self._find_missed_completions(memory)
            for task_id, pr_number in completed_missed:
                self._mark_task_complete(memory, task_id, pr_number)

            # Auto-fix simple issues
            fixed_count = 0
            for orphan in self.orphaned:
                if orphan.auto_fixable:
                    success = self._auto_fix(orphan, memory)
                    if success:
                        fixed_count += 1
                        report["actions_taken"].append(
                            {
                                "resource": orphan.resource_id,
                                "action": "auto_fixed",
                            }
                        )

            report["orphaned_found"] = [
                {
                    "type": o.resource_type,
                    "id": o.resource_id,
                    "reason": o.reason,
                    "auto_fixable": o.auto_fixable,
                }
                for o in self.orphaned
            ]

            report["fixed_count"] = fixed_count
            report["needs_manual_review"] = len(self.orphaned) - fixed_count

            self.audit.log_event(
                "reconciliation_complete",
                None,
                {
                    "orphaned_count": len(self.orphaned),
                    "fixed_count": fixed_count,
                },
            )

        except Exception as e:
            self.logger.error(f"Reconciliation error: {e}")
            report["errors"].append(str(e))

        report["completed_at"] = datetime.now().isoformat()
        return report

    def _find_orphaned_prs(self, memory: Dict) -> List[OrphanedResource]:
        """Find PRs that exist but aren't tracked in any task"""
        orphaned = []

        # Get tracked PRs
        tracked_prs: Set[int] = set()
        for task in memory.get("tasks", []):
            if task.get("pr_id"):
                tracked_prs.add(task["pr_id"])

        # Get all open PRs
        try:
            open_prs = self.github.list_prs(state="open")

            for pr in open_prs:
                pr_number = pr.get("number")
                pr_title = pr.get("title", "")

                # Check if it's an auto-created PR but not tracked
                if "[AUTO]" in pr_title and pr_number not in tracked_prs:
                    # Try to find which task it belongs to
                    task_id = self._extract_task_id(pr_title)

                    orphan = OrphanedResource(
                        resource_type="pr",
                        resource_id=f"PR #{pr_number}",
                        resource_number=pr_number,
                        detected_at=datetime.now().isoformat(),
                        reason=f"PR exists but not tracked in task {task_id or 'unknown'}",
                        suggested_action="Link to task or close",
                        auto_fixable=task_id is not None,
                    )
                    orphaned.append(orphan)

        except Exception as e:
            self.logger.error(f"Error finding orphaned PRs: {e}")

        return orphaned

    def _find_orphaned_issues(self, memory: Dict) -> List[OrphanedResource]:
        """Find issues that exist but tasks don't track them"""
        orphaned = []

        # Get tracked issues
        tracked_issues: Set[int] = set()
        for task in memory.get("tasks", []):
            if task.get("issue_id"):
                tracked_issues.add(task["issue_id"])

        # Get all open auto issues
        try:
            issues = self.github.list_issues(state="open", labels=["auto-task"])

            for issue in issues:
                issue_number = issue.get("number")
                issue_title = issue.get("title", "")

                if issue_number not in tracked_issues:
                    task_id = self._extract_task_id(issue_title)

                    # Check if task exists but doesn't track this issue
                    task_exists = (
                        any(t["id"] == task_id for t in memory.get("tasks", []))
                        if task_id
                        else False
                    )

                    orphan = OrphanedResource(
                        resource_type="issue",
                        resource_id=f"Issue #{issue_number}",
                        resource_number=issue_number,
                        detected_at=datetime.now().isoformat(),
                        reason=f"Open issue not tracked (task {task_id} may exist: {task_exists})",
                        suggested_action="Link to task or close if stale",
                        auto_fixable=task_exists,
                    )
                    orphaned.append(orphan)

        except Exception as e:
            self.logger.error(f"Error finding orphaned issues: {e}")

        return orphaned

    def _find_stuck_tasks(self, memory: Dict) -> List[Tuple[str, str]]:
        """Find tasks stuck in transient states for too long"""
        stuck = []

        for task in memory.get("tasks", []):
            status = task.get("status", "")
            last_change = task.get("last_state_change")

            if status in ["merging", "jules_triggered", "pr_opened"]:
                if last_change:
                    try:
                        last = datetime.fromisoformat(last_change)
                        age = (datetime.now() - last).total_seconds() / 60

                        # Thresholds for stuck detection
                        thresholds = {
                            "merging": 30,  # 30 minutes
                            "jules_triggered": 120,  # 2 hours
                            "pr_opened": 60,  # 1 hour
                        }

                        threshold = thresholds.get(status, 60)
                        if age > threshold:
                            stuck.append(
                                (task["id"], f"stuck in {status} for {age:.0f}m")
                            )
                    except Exception:
                        pass

        return stuck

    def _find_missed_completions(self, memory: Dict) -> List[Tuple[str, int]]:
        """Find PRs that are merged but tasks not marked complete"""
        missed = []

        for task in memory.get("tasks", []):
            if task["status"] in ["pr_opened", "approved", "merging"]:
                pr_id = task.get("pr_id")
                if pr_id:
                    try:
                        pr_info = self.github.get_pr(pr_id)
                        if pr_info and pr_info.get("merged"):
                            missed.append((task["id"], pr_id))
                    except Exception:
                        pass

        return missed

    def _attempt_stuck_recovery(self, memory: Dict, task_id: str, reason: str):
        """Attempt to recover a stuck task"""
        self.logger.info(f"Attempting recovery for stuck task {task_id}: {reason}")

        task = next((t for t in memory.get("tasks", []) if t["id"] == task_id), None)
        if not task:
            return

        status = task.get("status", "")

        if status == "merging":
            # Check if actually merged
            pr_id = task.get("pr_id")
            if pr_id:
                try:
                    pr_info = self.github.get_pr(pr_id)
                    if pr_info and pr_info.get("merged"):
                        task["status"] = "complete"
                        task["merged_at"] = datetime.now().isoformat()
                        self.logger.info(f"Recovered task {task_id} - PR was merged")
                except Exception as e:
                    self.logger.error(f"Failed to check merge status: {e}")

        elif status == "jules_triggered":
            # Check if PR was created
            pr_info = None
            try:
                # Try to find PR by task ID
                from github_utils import find_pr_by_task_id

                pr_info = find_pr_by_task_id(self.github, task_id, task.get("issue_id"))
            except Exception:
                pass

            if pr_info:
                task["status"] = "pr_opened"
                task["pr_id"] = pr_info["number"]
                self.logger.info(
                    f"Recovered task {task_id} - PR found: #{pr_info['number']}"
                )

    def _mark_task_complete(self, memory: Dict, task_id: str, pr_number: int):
        """Mark a task as complete"""
        for task in memory.get("tasks", []):
            if task["id"] == task_id:
                task["status"] = "complete"
                task["pr_id"] = pr_number
                task["merged_at"] = datetime.now().isoformat()
                self.logger.info(f"Marked task {task_id} as complete (PR #{pr_number})")
                break

    def _extract_task_id(self, title: str) -> Optional[str]:
        """Extract task ID from PR/issue title"""
        import re

        match = re.search(r"\[([A-Z]\d+)\]", title)
        return match.group(1) if match else None

    def _auto_fix(self, orphan: OrphanedResource, memory: Dict) -> bool:
        """Attempt to auto-fix an orphaned resource"""
        try:
            if orphan.resource_type == "pr" and orphan.resource_number:
                # Link to task if possible
                task_id = self._extract_task_id(orphan.resource_id)
                if task_id:
                    for task in memory.get("tasks", []):
                        if task["id"] == task_id and not task.get("pr_id"):
                            task["pr_id"] = orphan.resource_number
                            task["status"] = "pr_opened"
                            return True

            elif orphan.resource_type == "issue" and orphan.resource_number:
                # Link to task if possible
                task_id = self._extract_task_id(orphan.resource_id)
                if task_id:
                    for task in memory.get("tasks", []):
                        if task["id"] == task_id and not task.get("issue_id"):
                            task["issue_id"] = orphan.resource_number
                            return True

            return False
        except Exception as e:
            self.logger.error(f"Auto-fix failed: {e}")
            return False

    def get_orphaned_report(self) -> str:
        """Generate human-readable orphaned report"""
        lines = [
            "=" * 60,
            "RECONCILIATION REPORT",
            "=" * 60,
            f"\nTotal orphaned resources: {len(self.orphaned)}\n",
        ]

        if not self.orphaned:
            lines.append("✅ No orphaned resources found!")
            return "\n".join(lines)

        # Group by type
        by_type = {}
        for o in self.orphaned:
            by_type.setdefault(o.resource_type, []).append(o)

        for rtype, items in by_type.items():
            lines.append(f"\n{rtype.upper()}S ({len(items)}):")
            lines.append("-" * 40)
            for item in items:
                lines.append(f"  • {item.resource_id}")
                lines.append(f"    Reason: {item.reason}")
                lines.append(f"    Action: {item.suggested_action}")
                lines.append(f"    Auto-fix: {'Yes' if item.auto_fixable else 'No'}")
                lines.append("")

        return "\n".join(lines)


if __name__ == "__main__":
    # Test
    print("ReconciliationEngine created successfully")
    print("Run with actual GitHub client for full testing")
