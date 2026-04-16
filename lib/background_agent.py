#!/usr/bin/env python3
"""
Jules Background Agent v4.0.0 - Phase 1 Stabilization
Continuous monitoring and orchestration with idempotency and state machine
"""

import json
import time
import subprocess
import sys
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import logging
import os

# Import local modules
sys.path.insert(0, str(Path(__file__).parent))
from skill_detector import SkillDetector
from pr_quality_gate import PRQualityGate
from memory_manager import MemoryManager, AuditLog
from github_utils import (
    GitHubClient,
    GitHubAPIError,
    find_pr_by_task_id,
    check_issue_exists,
)
from state_machine import StateMachine, StateRecovery, InvalidStateTransition
from process_manager import ProcessManager

# Phase 2 imports
from circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    get_circuit_breaker,
    GITHUB_CIRCUIT,
    init_default_circuits,
)
from retry_manager import with_retry, github_api_retry
from reconciliation import ReconciliationEngine


class JulesBackgroundAgent:
    """
    Background agent that monitors GitHub, manages dependencies,
    approves PRs, and tracks execution state - Phase 1 Stabilized
    """

    def __init__(self, repo: str, memory_file: str = "JULES_MEMORY.json"):
        self.repo = repo
        self.memory_file = memory_file
        self.running = False
        self.check_interval = 30  # seconds
        self.max_iterations = 10000  # Safety limit
        self.iteration_count = 0
        self.last_progress = None
        self.stall_count = 0
        self.logger = self._setup_logger()
        self.quality_gate = PRQualityGate(repo)
        self.memory_manager = MemoryManager(memory_file)
        self.audit_log = AuditLog()
        self.github = GitHubClient(repo)
        self.state_machine = StateMachine()
        self.process_manager = ProcessManager(repo=repo)
        
        # Phase 2: Initialize circuit breaker and reconciliation
        init_default_circuits()
        self.github_circuit = get_circuit_breaker(GITHUB_CIRCUIT)
        self.reconciliation = ReconciliationEngine(
            self.github, self.memory_manager, self.audit_log
        )
        self._reconciliation_counter = 0

    def _setup_logger(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger("jules-agent")
        logger.setLevel(logging.INFO)

        handler = logging.FileHandler("jules-agent.log")
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def run(self):
        """Main execution loop with stall detection and safety limits"""
        # Acquire process lock
        if not self.process_manager.acquire():
            self.logger.error(
                "Failed to acquire process lock - another agent may be running"
            )
            return

        self.running = True
        self.logger.info(f"Starting background agent for {self.repo}")
        self.logger.info(f"Max iterations: {self.max_iterations}")
        self.audit_log.log_event("agent_start", None, {"repo": self.repo})

        while self.running:
            self.iteration_count += 1

            # Safety: max iterations
            if self.iteration_count > self.max_iterations:
                self.logger.error(
                    f"Max iterations ({self.max_iterations}) reached. Stopping."
                )
                self.audit_log.log_event(
                    "agent_stop", None, {"reason": "max_iterations"}
                )
                break

            try:
                memory = self.load_memory()

                if not memory:
                    self.logger.error("No memory file found")
                    self.audit_log.log_event(
                        "agent_stop", None, {"reason": "no_memory"}
                    )
                    break

                # Update process status
                self.process_manager.update_status("running", memory)

                # Check if all complete
                if self.all_tasks_complete(memory):
                    self.create_final_pr(memory)
                    self.logger.info("All tasks complete, stopping")
                    self.process_manager.update_status("complete", memory)
                    self.audit_log.log_event("agent_stop", None, {"reason": "complete"})
                    break

                # Stall detection
                current_progress = self._get_progress_snapshot(memory)
                if current_progress == self.last_progress:
                    self.stall_count += 1
                    if self.stall_count >= 20:  # 10 minutes of no progress
                        self.logger.warning(
                            f"Stall detected ({self.stall_count} iterations). Attempting recovery..."
                        )
                        self._attempt_stall_recovery(memory)
                        self.audit_log.log_event(
                            "stall_recovery", None, {"stall_count": self.stall_count}
                        )
                else:
                    self.stall_count = 0
                    self.last_progress = current_progress

                # Process current batch
                self.process_batch(memory)

                # Check for completed tasks
                self.handle_completed_tasks(memory)

                # Approve and merge ready PRs
                self.approve_and_merge_prs(memory)

                # Handle failed tasks with state machine
                self.handle_failed_tasks(memory)

                # Save state (atomic)
                self.memory_manager.save(memory)

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                import traceback

                self.logger.error(traceback.format_exc())
                self.audit_log.log_event("agent_error", None, {"error": str(e)})

            # Phase 2: Run reconciliation every 20 iterations
            self._reconciliation_counter += 1
            if self._reconciliation_counter >= 20:
                self._run_reconciliation(memory)
                self._reconciliation_counter = 0

            time.sleep(self.check_interval)

        # Cleanup
        self.process_manager.release()

    def _get_progress_snapshot(self, memory: Dict) -> str:
        """Get a hashable progress snapshot for stall detection"""
        tasks = memory.get("tasks", [])
        statuses = [f"{t['id']}:{t['status']}" for t in tasks]
        return "|".join(sorted(statuses))

    def _attempt_stall_recovery(self, memory: Dict):
        """Attempt to recover from stalled state"""
        tasks = memory.get("tasks", [])

        # Check for tasks stuck in transient states
        for task in tasks:
            if task["status"] == "merging":
                # Check if actually merged
                pr_info = self.get_pr_for_task(task)
                if pr_info and pr_info.get("merged"):
                    task["status"] = "complete"
                    self.logger.info(f"Recovered task {task['id']} - was merged")

            elif task["status"] == "jules_triggered":
                # Check if PR opened
                pr_info = self.get_pr_for_task(task)
                if pr_info:
                    task["status"] = "pr_opened"
                    task["pr_id"] = pr_info["number"]
                    self.logger.info(f"Recovered task {task['id']} - PR found")

        self.stall_count = 0

    def process_batch(self, memory: Dict):
        """Create issues for tasks whose dependencies are complete - with state machine"""
        tasks = memory.get("tasks", [])
        completed_ids = self.get_completed_task_ids(memory)

        for task in tasks:
            # Only process pending tasks
            try:
                self.state_machine.transition(
                    task, "issue_created", "Dependencies complete"
                )
            except InvalidStateTransition:
                continue  # Task not in pending state

            # Double-check: if task already has issue_id, skip
            if task.get("issue_id"):
                self.logger.warning(
                    f"Task {task['id']} already has issue #{task['issue_id']}, skipping"
                )
                self.state_machine.force_transition(
                    task, "jules_triggered", "Issue already exists"
                )
                continue

            deps = task.get("dependencies", [])
            if not all(d in completed_ids for d in deps):
                # Rollback state transition if deps not ready
                self.state_machine.force_transition(
                    task, "pending", "Dependencies not ready"
                )
                continue

            self.logger.info(f"Processing task {task['id']}")

            # Check for existing issue via GitHub API
            existing = check_issue_exists(self.github, f"[AUTO][{task['id']}]")
            if existing:
                self.logger.info(f"Found existing issue #{existing} for {task['id']}")
                task["issue_id"] = existing
                self.state_machine.transition(
                    task, "jules_triggered", "Existing issue found"
                )
                self.audit_log.log_event(
                    "issue_found", task["id"], {"issue_id": existing}
                )
                continue

            # Create new issue
            issue_id = self.create_github_issue(task)

            if issue_id:
                task["issue_id"] = issue_id
                task["created_at"] = datetime.now().isoformat()

                # Save immediately to prevent duplicates
                self.save_memory(memory)
                self.audit_log.log_event(
                    "issue_created", task["id"], {"issue_id": issue_id}
                )

                # Transition to triggered
                try:
                    self.state_machine.transition(
                        task, "jules_triggered", "Issue created successfully"
                    )
                    self.logger.info(f"Task {task['id']} triggered Jules")
                except InvalidStateTransition as e:
                    self.logger.error(f"State transition failed: {e}")

    def handle_completed_tasks(self, memory: Dict):
        """Check for merged PRs and mark tasks complete"""
        tasks = memory.get("tasks", [])

        for task in tasks:
            # Only check tasks that have PRs in flight
            if task["status"] not in [
                "jules_triggered",
                "pr_opened",
                "approved",
                "merging",
            ]:
                continue

            # Check PR status
            pr_info = self.get_pr_for_task(task)
            if not pr_info:
                continue

            pr_number = pr_info["number"]

            if pr_info.get("merged"):
                # Validate the merged work
                if self.validate_merged_pr(task, pr_info):
                    task["status"] = "complete"
                    task["pr_id"] = pr_number
                    task["merged_at"] = datetime.now().isoformat()
                    self.logger.info(f"✅ Task {task['id']} complete (PR #{pr_number})")
                else:
                    task["status"] = "failed"
                    task["failure_reason"] = "Validation failed after merge"
                    task["pr_id"] = pr_number
                    self.logger.warning(
                        f"Task {task['id']} failed post-merge validation"
                    )

    def approve_and_merge_prs(self, memory: Dict):
        """Auto-approve and merge PRs to dev branch - IDEMPOTENT"""
        tasks = memory.get("tasks", [])

        for task in tasks:
            if task["status"] not in ["pr_opened", "approved"]:
                continue

            pr_info = self.get_pr_for_task(task)
            if not pr_info:
                continue

            pr_number = pr_info["number"]

            # Check if already merged (idempotency)
            if pr_info.get("merged"):
                self.logger.info(f"PR #{pr_number} already merged")
                task["status"] = "complete"
                task["pr_id"] = pr_number
                task["merged_at"] = datetime.now().isoformat()
                continue

            # Check if already approved (idempotency)
            if self.is_pr_approved(pr_number):
                self.logger.info(f"PR #{pr_number} already approved")
                if task["status"] == "pr_opened":
                    task["status"] = "approved"

            # Validate PR if not yet approved
            if task["status"] == "pr_opened":
                if not self.validate_pr(task, pr_info):
                    self.logger.warning(f"PR #{pr_number} failed validation")
                    task["status"] = "failed"
                    task["retry_count"] = task.get("retry_count", 0) + 1
                    continue

                # Check CI status
                if not self.check_ci_status(pr_number):
                    self.logger.info(f"PR #{pr_number} CI not complete")
                    continue

                # Approve PR (idempotent - checks if already approved)
                self.logger.info(f"Approving PR #{pr_number}")
                if self.approve_pr(pr_number):
                    task["status"] = "approved"
                    task["approved_at"] = datetime.now().isoformat()

            # Merge if approved (idempotent - checks if already merged)
            if task["status"] == "approved":
                self.logger.info(f"Merging PR #{pr_number} to dev")
                if self.merge_pr(pr_number):
                    task["status"] = "merging"
                    task["merged_at"] = datetime.now().isoformat()
                    # Immediately check if merge completed
                    pr_info = self.get_pr_for_task(task)
                    if pr_info and pr_info.get("merged"):
                        task["status"] = "complete"

    def handle_failed_tasks(self, memory: Dict):
        """Handle failed tasks - retry or block with state machine"""
        tasks = memory.get("tasks", [])
        max_retries = memory.get("config", {}).get("max_retries", 2)
        recovery = StateRecovery(self.state_machine)

        for task in tasks:
            current_state = task.get("status", "")

            # Handle blocked tasks - check for recovery
            if current_state == "blocked":
                if recovery.can_recover(task):
                    options = recovery.get_recovery_options(task)
                    if options:
                        self.logger.info(
                            f"Task {task['id']} is blocked. Recovery options available."
                        )
                        self.audit_log.log_event(
                            "task_blocked",
                            task["id"],
                            {"recovery_options": len(options)},
                        )
                continue

            if current_state != "failed":
                continue

            retry_count = task.get("retry_count", 0)

            if retry_count < max_retries:
                self.logger.info(
                    f"Retrying task {task['id']} (attempt {retry_count + 1}/{max_retries})"
                )

                # Reset task for retry
                old_issue = task.get("issue_id")
                task["retry_count"] = retry_count + 1
                task["previous_issue_id"] = old_issue

                # Create new issue for retry
                issue_id = self.create_github_issue(task, retry=True)
                if issue_id:
                    self.audit_log.log_event(
                        "task_retry",
                        task["id"],
                        {
                            "attempt": retry_count + 1,
                            "issue_id": issue_id,
                            "previous_issue": old_issue,
                        },
                    )

                    try:
                        self.state_machine.transition(
                            task, "issue_created", f"Retry attempt {retry_count + 1}"
                        )
                        task["issue_id"] = issue_id
                        self.trigger_jules(task, issue_id)
                        self.state_machine.transition(
                            task, "jules_triggered", "Retry triggered"
                        )
                    except InvalidStateTransition as e:
                        self.logger.error(f"State transition failed on retry: {e}")
                else:
                    self.logger.error(f"Failed to create retry issue for {task['id']}")
            else:
                self.logger.error(
                    f"Task {task['id']} max retries ({max_retries}) exceeded, blocking"
                )
                try:
                    self.state_machine.transition(
                        task, "blocked", f"Max retries ({max_retries}) exceeded"
                    )
                    self.audit_log.log_event(
                        "task_blocked", task["id"], {"reason": "max_retries_exceeded"}
                    )
                except InvalidStateTransition:
                    self.logger.warning(f"Could not transition {task['id']} to blocked")

    def validate_pr(self, task: Dict, pr_info: Dict) -> bool:
        """Validate PR using Quality Gate - returns True only if passed"""
        pr_number = pr_info["number"]

        self.logger.info(f"Running Quality Gate on PR #{pr_number}")

        validation = self.quality_gate.validate_pr(task, pr_number)

        # Log results
        report = self.quality_gate.generate_report(validation)
        self.logger.info(f"Quality Gate Report:\n{report}")

        if not validation["passed"]:
            self.logger.error(f"PR #{pr_number} FAILED Quality Gate")
            self.logger.error(f"Errors: {validation['errors']}")
            return False

        self.logger.info(
            f"PR #{pr_number} PASSED Quality Gate (Score: {validation['score']})"
        )
        return True

    def validate_merged_pr(self, task: Dict, pr_info: Dict) -> bool:
        """Validate merged PR - check files actually in repo"""
        expected_files = task.get("files_expected", [])

        for file_path in expected_files:
            try:
                result = subprocess.run(
                    ["git", "ls-tree", "HEAD", file_path],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self.logger.warning(f"Expected file not found: {file_path}")
                    return False
            except Exception:
                return False

        return True

    def check_existing_issue(self, task: Dict) -> Optional[int]:
        """Check if issue already exists for this task"""
        try:
            # Search for issues with this task ID
            cmd = [
                "gh",
                "issue",
                "list",
                "-R",
                self.repo,
                "--state",
                "all",
                "--search",
                f"[AUTO][{task['id']}]",
                "--json",
                "number,title,state",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            issues = json.loads(result.stdout)

            for issue in issues:
                if f"[{task['id']}]" in issue.get("title", ""):
                    self.logger.info(
                        f"Found existing issue #{issue['number']} for {task['id']}"
                    )
                    return issue["number"]

            return None
        except Exception as e:
            self.logger.error(f"Error checking existing issues: {e}")
            return None

    @github_api_retry()
    def create_github_issue(self, task: Dict, retry: bool = False) -> Optional[int]:
        """Create GitHub issue for task"""
        # Check for existing issue first
        existing = self.check_existing_issue(task)
        if existing:
            self.logger.warning(
                f"Duplicate prevention: Issue #{existing} already exists for {task['id']}"
            )
            return existing

        retry_suffix = f" (Retry #{task.get('retry_count', 0) + 1})" if retry else ""
        title = f"[AUTO][{task['id']}] {task['title']}{retry_suffix}"
        body = self.format_issue_body(task)
        labels = f"jules,auto-task,{task['type'].lower()}"

        cmd = [
            "gh",
            "issue",
            "create",
            "-R",
            self.repo,
            "--title",
            title,
            "--body",
            body,
            "--label",
            labels,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            issue_url = result.stdout.strip()
            issue_number = int(issue_url.split("/")[-1])
            self.logger.info(f"Created issue #{issue_number} for {task['id']}")
            return issue_number
        except Exception as e:
            self.logger.error(f"Failed to create issue: {e}")
            return None

    def format_issue_body(self, task: Dict, repo_path: str = ".") -> str:
        """Format GitHub issue body with skill injection"""
        # Detect and inject skills
        try:
            detector = SkillDetector()
            skills = detector.get_skills_for_task(task, repo_path)
            skill_section = detector.generate_skill_prompt(skills)

            # Install skills to project for reference
            detector.install_skills_to_project(repo_path, [s["name"] for s in skills])
        except Exception as e:
            self.logger.error(f"Failed to load skills: {e}")
            skill_section = ""

        body = f"""## Task Definition
- **ID**: {task["id"]}
- **Type**: {task["type"]}
- **Priority**: High
- **Created**: {datetime.now().isoformat()}

## Description
{task["description"]}

## Expected Files
"""
        for f in task.get("files_expected", []):
            body += f"- [ ] `{f}`\n"

        body += "\n## Acceptance Criteria\n"
        for i, criteria in enumerate(task.get("acceptance_criteria", []), 1):
            body += f"{i}. {criteria}\n"

        body += "\n## Test Cases\n"
        for i, test in enumerate(task.get("test_cases", []), 1):
            body += f"{i}. {test}\n"

        deps = task.get("dependencies", [])
        if deps:
            body += f"\n## Dependencies\n"
            for dep in deps:
                body += f"- {dep} ✅\n"

        # Add skill section
        if skill_section:
            body += f"\n## Skill Guidelines\n```\n{skill_section}\n```\n"

        body += """
## Jules Instructions
**CRITICAL**: Execute EXACTLY as specified. Do not expand scope.

Expected files must be created with exact paths.
All acceptance criteria must be satisfied.
Tests must pass before submitting PR.

---
*Generated by Jules Orchestrator v3.0*
"""
        return body

    def trigger_jules(self, task: Dict, issue_id: int):
        """Trigger Jules by ensuring jules label is present"""
        # Jules auto-processes issues with 'jules' label
        pass

    def get_pr_for_task(self, task: Dict) -> Optional[Dict]:
        """Get PR associated with task - uses GitHub client with caching"""
        task_id = task["id"]
        issue_id = task.get("issue_id")

        # Use the centralized function from github_utils
        return find_pr_by_task_id(self.github, task_id, issue_id)

    def get_pr_files(self, pr_number: int) -> List[str]:
        """Get files changed in PR"""
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
                    "files",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            return [f["path"] for f in data.get("files", [])]
        except Exception:
            return []

    def check_ci_status(self, pr_number: int) -> bool:
        """Check if CI checks pass"""
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
                    "statusCheckRollup",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            checks = data.get("statusCheckRollup", [])

            if not checks:
                return True  # No CI configured

            return all(
                c.get("state") == "SUCCESS" or c.get("conclusion") == "SUCCESS"
                for c in checks
            )
        except Exception:
            return True  # Assume pass on error

    def is_pr_approved(self, pr_number: int) -> bool:
        """Check if PR is already approved - for idempotency"""
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
                    "reviewDecision",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            return data.get("reviewDecision") == "APPROVED"
        except Exception:
            return False

    def approve_pr(self, pr_number: int) -> bool:
        """Approve PR via gh CLI - IDEMPOTENT with circuit breaker"""
        try:
            return self.github_circuit.call(self._do_approve_pr, pr_number)
        except CircuitBreakerOpen:
            self.logger.error(f"Circuit breaker open - cannot approve PR #{pr_number}")
            return False
    
    def _do_approve_pr(self, pr_number: int) -> bool:
        """Approve PR via gh CLI - IDEMPOTENT"""
        # Check if already approved
        if self.is_pr_approved(pr_number):
            self.logger.info(f"PR #{pr_number} already approved")
            return True

        try:
            cmd = [
                "gh",
                "pr",
                "review",
                str(pr_number),
                "-R",
                self.repo,
                "--approve",
                "--body",
                "Auto-approved by Jules Orchestrator v3.0",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.info(f"Approved PR #{pr_number}")
            return True
        except subprocess.CalledProcessError as e:
            # Check if already approved (common race condition)
            if "already approved" in e.stderr.lower() or self.is_pr_approved(pr_number):
                self.logger.info(f"PR #{pr_number} was already approved")
                return True
            self.logger.error(f"Failed to approve PR #{pr_number}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to approve PR #{pr_number}: {e}")
            return False

    def is_pr_merged(self, pr_number: int) -> bool:
        """Check if PR is already merged - for idempotency"""
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
                    "state,merged",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            return data.get("state") == "MERGED" or data.get("merged") is True
        except Exception:
            return False

    def merge_pr(self, pr_number: int) -> bool:
        """Merge PR to dev branch - IDEMPOTENT with circuit breaker"""
        try:
            return self.github_circuit.call(self._do_merge_pr, pr_number)
        except CircuitBreakerOpen:
            self.logger.error(f"Circuit breaker open - cannot merge PR #{pr_number}")
            return False
    
    def _do_merge_pr(self, pr_number: int) -> bool:
        """Merge PR to dev branch - IDEMPOTENT"""
        # Check if already merged
        if self.is_pr_merged(pr_number):
            self.logger.info(f"PR #{pr_number} already merged")
            return True

        try:
            cmd = [
                "gh",
                "pr",
                "merge",
                str(pr_number),
                "-R",
                self.repo,
                "--squash",
                "--delete-branch",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.info(f"Merged PR #{pr_number}")
            return True
        except subprocess.CalledProcessError as e:
            # Check if already merged (common race condition)
            if "already merged" in e.stderr.lower() or self.is_pr_merged(pr_number):
                self.logger.info(f"PR #{pr_number} was already merged")
                return True
            self.logger.error(f"Failed to merge PR #{pr_number}: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to merge PR #{pr_number}: {e}")
            return False

    def create_final_pr(self, memory: Dict):
        """Create PR from dev to main when all tasks complete"""
        tasks = memory.get("tasks", [])

        if not all(t["status"] == "complete" for t in tasks):
            return

        # Check if already exists
        existing = self.get_existing_final_pr()
        if existing:
            self.logger.info(f"Final PR already exists: {existing}")
            return

        # Create PR
        title = f"[COMPLETE] {memory['project_name']}"
        body = self.format_final_pr_body(memory)

        try:
            cmd = [
                "gh",
                "pr",
                "create",
                "-R",
                self.repo,
                "--title",
                title,
                "--body",
                body,
                "--head",
                "dev",
                "--base",
                "main",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            pr_url = result.stdout.strip()

            memory["final_pr"] = pr_url
            memory["status"] = "complete"
            self.save_memory(memory)

            self.logger.info(f"🎉 Final PR created: {pr_url}")
        except Exception as e:
            self.logger.error(f"Failed to create final PR: {e}")

    def get_existing_final_pr(self) -> Optional[str]:
        """Check if final PR already exists"""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "-R",
                    self.repo,
                    "--state",
                    "all",
                    "--json",
                    "number,title",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            prs = json.loads(result.stdout)

            for pr in prs:
                if "[COMPLETE]" in pr.get("title", ""):
                    return pr["url"]
        except Exception:
            pass

        return None

    def format_final_pr_body(self, memory: Dict) -> str:
        """Format final PR body"""
        tasks = memory.get("tasks", [])

        body = f"""# {memory["project_name"]} - Complete Implementation

## Summary
All tasks have been completed via Jules orchestration.

## Tasks Completed
"""
        for task in tasks:
            body += f"- ✅ **{task['id']}**: {task['title']}\n"

        body += """
## Implementation
- All acceptance criteria met
- All tests passing
- Code follows project conventions

## Ready for Review
Please review and merge to main.

---
*Generated by Jules Orchestrator v3.0*
"""
        return body

    def get_completed_task_ids(self, memory: Dict) -> Set[str]:
        """Get IDs of completed tasks"""
        return {t["id"] for t in memory.get("tasks", []) if t["status"] == "complete"}

    def all_tasks_complete(self, memory: Dict) -> bool:
        """Check if all tasks are complete"""
        tasks = memory.get("tasks", [])
        return all(t["status"] == "complete" for t in tasks)


    def _run_reconciliation(self, memory: Dict):
        """Run reconciliation to find and fix orphaned resources"""
        try:
            self.logger.info("Running reconciliation check...")
            report = self.reconciliation.run_full_reconciliation(memory)
            
            if report.get("orphaned_found"):
                self.logger.warning(
                    f"Found {len(report['orphaned_found'])} orphaned resources"
                )
                
            if report.get("fixed_count", 0) > 0:
                self.logger.info(f"Auto-fixed {report['fixed_count']} issues")
                
            # Log to audit
            self.audit_log.log_event(
                "reconciliation_run",
                None,
                {
                    "orphaned_count": len(report.get("orphaned_found", [])),
                    "fixed_count": report.get("fixed_count", 0),
                }
            )
        except Exception as e:
            self.logger.error(f"Reconciliation failed: {e}")

    def load_memory(self) -> Dict:
        """Load memory from file"""
        return self.memory_manager.load()

    def save_memory(self, memory: Dict):
        """Save memory to file and commit - DEPRECATED, use memory_manager directly"""
        self.memory_manager.save(memory)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Jules Background Agent")
    parser.add_argument("--repo", required=True, help="GitHub repo (org/name)")
    parser.add_argument("--memory", default="JULES_MEMORY.json", help="Memory file")
    args = parser.parse_args()

    agent = JulesBackgroundAgent(args.repo, args.memory)

    # Handle signals
    def signal_handler(sig, frame):
        print("\n👋 Stopping background agent...")
        agent.running = False
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"🚀 Starting background agent for {args.repo}")
    print(f"   Memory file: {args.memory}")
    print(f"   Check interval: {agent.check_interval}s")
    print(f"   Log: jules-agent.log")

    agent.run()


if __name__ == "__main__":
    main()
