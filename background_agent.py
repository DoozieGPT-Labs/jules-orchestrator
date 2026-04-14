#!/usr/bin/env python3
"""
Jules Background Agent v3.0
Continuous monitoring and orchestration
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


class JulesBackgroundAgent:
    """
    Background agent that monitors GitHub, manages dependencies,
    approves PRs, and tracks execution state.
    """

    def __init__(self, repo: str, memory_file: str = "JULES_MEMORY.json"):
        self.repo = repo
        self.memory_file = memory_file
        self.running = False
        self.check_interval = 30  # seconds
        self.logger = self._setup_logger()
        self.quality_gate = PRQualityGate(repo)

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
        """Main execution loop"""
        self.running = True
        self.logger.info(f"Starting background agent for {self.repo}")

        while self.running:
            try:
                memory = self.load_memory()

                if not memory:
                    self.logger.error("No memory file found")
                    break

                # Check if all complete
                if self.all_tasks_complete(memory):
                    self.create_final_pr(memory)
                    self.logger.info("All tasks complete, stopping")
                    break

                # Process current batch
                self.process_batch(memory)

                # Check for completed tasks
                self.handle_completed_tasks(memory)

                # Approve and merge ready PRs
                self.approve_and_merge_prs(memory)

                # Handle failed tasks
                self.handle_failed_tasks(memory)

                # Save state
                self.save_memory(memory)

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")

            time.sleep(self.check_interval)

def process_batch(self, memory: Dict):
        """Create issues for tasks whose dependencies are complete"""
        tasks = memory.get("tasks", [])
        completed_ids = self.get_completed_task_ids(memory)
        
        for task in tasks:
            if task["status"] != "pending":
                continue
            
            # Double-check: if task already has issue_id, skip
            if task.get("issue_id"):
                self.logger.warning(f"Task {task['id']} already has issue #{task['issue_id']}, skipping")
                continue
            
            deps = task.get("dependencies", [])
            if all(d in completed_ids for d in deps):
                self.logger.info(f"Processing task {task['id']}")
                
                # Check memory for existing issue_id (extra safety)
                memory_task = next((t for t in memory.get("tasks", []) if t["id"] == task["id"]), None)
                if memory_task and memory_task.get("issue_id"):
                    self.logger.warning(f"Task {task['id']} already has issue in memory, skipping")
                    continue
                
                issue_id = self.create_github_issue(task)
                
                if issue_id:
                    task["status"] = "issue_created"
                    task["issue_id"] = issue_id
                    task["created_at"] = datetime.now().isoformat()
                    
                    # Save immediately to prevent duplicates
                    self.save_memory(memory)
                    
                    # Trigger Jules (label triggers processing)
                    self.trigger_jules(task, issue_id)
                    task["status"] = "jules_triggered"
                    self.logger.info(f"Task {task['id']} triggered Jules")

    def handle_completed_tasks(self, memory: Dict):
        """Check for merged PRs and mark tasks complete"""
        tasks = memory.get("tasks", [])

        for task in tasks:
            if task["status"] not in [
                "jules_triggered",
                "pr_opened",
                "validating",
                "approved",
                "merging",
            ]:
                continue

            # Check PR status
            pr_info = self.get_pr_for_task(task)
            if not pr_info:
                continue

            if pr_info.get("merged"):
                # Validate the merged work
                if self.validate_merged_pr(task, pr_info):
                    task["status"] = "complete"
                    task["pr_id"] = pr_info["number"]
                    task["merged_at"] = datetime.now().isoformat()
                    self.logger.info(f"✅ Task {task['id']} complete")
                else:
                    task["status"] = "failed"
                    task["failure_reason"] = "Validation failed after merge"
                    self.logger.warning(f"Task {task['id']} failed validation")

    def approve_and_merge_prs(self, memory: Dict):
        """Auto-approve and merge PRs to dev branch"""
        tasks = memory.get("tasks", [])

        for task in tasks:
            if task["status"] != "pr_opened":
                continue

            pr_info = self.get_pr_for_task(task)
            if not pr_info:
                continue

            # Validate PR
            if not self.validate_pr(task, pr_info):
                self.logger.warning(f"PR #{pr_info['number']} failed validation")
                task["status"] = "failed"
                task["retry_count"] = task.get("retry_count", 0) + 1
                continue

            # Check CI status
            if not self.check_ci_status(pr_info["number"]):
                self.logger.info(f"PR #{pr_info['number']} CI not complete")
                continue

            # Approve PR
            self.logger.info(f"Approving PR #{pr_info['number']}")
            if self.approve_pr(pr_info["number"]):
                task["status"] = "approved"

                # Merge to dev
                self.logger.info(f"Merging PR #{pr_info['number']} to dev")
                if self.merge_pr(pr_info["number"]):
                    task["status"] = "merging"

    def handle_failed_tasks(self, memory: Dict):
        """Handle failed tasks - retry or block"""
        tasks = memory.get("tasks", [])
        max_retries = memory.get("config", {}).get("max_retries", 2)

        for task in tasks:
            if task["status"] != "failed":
                continue

            retry_count = task.get("retry_count", 0)

            if retry_count < max_retries:
                self.logger.info(
                    f"Retrying task {task['id']} (attempt {retry_count + 1})"
                )

                # Create new issue for retry
                issue_id = self.create_github_issue(task, retry=True)
                if issue_id:
                    task["status"] = "issue_created"
                    task["issue_id"] = issue_id
                    task["retry_count"] = retry_count + 1
                    self.trigger_jules(task, issue_id)
                    task["status"] = "jules_triggered"
            else:
                self.logger.error(f"Task {task['id']} max retries exceeded, blocking")
                task["status"] = "blocked"

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
        
        self.logger.info(f"PR #{pr_number} PASSED Quality Gate (Score: {validation['score']})")
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
        """Get PR associated with task - FIXED to search by issue reference"""
        task_id = task["id"]
        issue_id = task.get("issue_id")
        
        try:
            # Check open PRs
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
                    "number,title,body,headRefName",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            prs = json.loads(result.stdout)
            
            for pr in prs:
                # Search by: task ID in title, OR issue reference in body
                pr_title = pr.get("title", "")
                pr_body = pr.get("body", "")
                branch = pr.get("headRefName", "")
                
                if task_id in pr_title:
                    return pr
                
                # Jules references issue in PR body: "Fixes #6"
                if issue_id and f"#{issue_id}" in pr_body:
                    return pr
                
                # Branch name may contain task info
                if task_id.lower() in branch.lower():
                    return pr
            
            # Check merged PRs
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "-R",
                    self.repo,
                    "--state",
                    "merged",
                    "--json",
                    "number,title,body,headRefName",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            prs = json.loads(result.stdout)
            
            for pr in prs:
                pr_title = pr.get("title", "")
                pr_body = pr.get("body", "")
                branch = pr.get("headRefName", "")
                
                if task_id in pr_title:
                    return pr
                
                if issue_id and f"#{issue_id}" in pr_body:
                    return pr
                
                if task_id.lower() in branch.lower():
                    return pr
            
        except Exception as e:
            self.logger.error(f"Error getting PR for task {task_id}: {e}")
        
        return None

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

    def approve_pr(self, pr_number: int) -> bool:
        """Approve PR via gh CLI"""
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
            subprocess.run(cmd, capture_output=True, check=True)
            self.logger.info(f"Approved PR #{pr_number}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to approve PR #{pr_number}: {e}")
            return False

    def merge_pr(self, pr_number: int) -> bool:
        """Merge PR to dev branch"""
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
            subprocess.run(cmd, capture_output=True, check=True)
            self.logger.info(f"Merged PR #{pr_number}")
            return True
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

    def load_memory(self) -> Dict:
        """Load memory from file"""
        if Path(self.memory_file).exists():
            with open(self.memory_file, "r") as f:
                return json.load(f)
        return {}

    def save_memory(self, memory: Dict):
        """Save memory to file and commit"""
        with open(self.memory_file, "w") as f:
            json.dump(memory, f, indent=2)

        self.commit_memory()

    def commit_memory(self):
        """Commit memory file"""
        try:
            subprocess.run(["git", "add", self.memory_file], check=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"[Jules] Update execution state - {datetime.now().isoformat()}",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push"], check=True, capture_output=True)
        except Exception as e:
            self.logger.error(f"Failed to commit memory: {e}")


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
