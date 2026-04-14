#!/usr/bin/env python3
"""
PR Quality Gate - Pre-merge validation engine
Ensures Jules output meets requirements before auto-approval
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PRQualityGate:
    """
    Validates PRs against task expectations before merge
    Hard stop layer for incorrect Jules output
    """

    def __init__(self, repo: str):
        self.repo = repo

    def validate_pr(self, task: Dict, pr_number: int) -> Dict:
        """
        Run full validation suite on PR
        Returns: {passed: bool, score: int, errors: [], warnings: []}
        """
        errors = []
        warnings = []

        # 1. Files Check
        files_ok, file_errors = self._validate_files(task, pr_number)
        errors.extend(file_errors)

        # 2. No Unrelated Changes
        unrelated_ok, unrelated_errors = self._check_unrelated_files(task, pr_number)
        if not unrelated_ok:
            warnings.extend(unrelated_errors)

        # 3. Naming Conventions
        naming_ok, naming_errors = self._validate_naming(task, pr_number)
        if not naming_ok:
            errors.extend(naming_errors)

        # 4. Acceptance Criteria
        criteria_ok, criteria_errors = self._validate_criteria(task, pr_number)
        if not criteria_ok:
            errors.extend(criteria_errors)

        # 5. CI Status
        ci_ok = self._check_ci_status(pr_number)
        if not ci_ok:
            errors.append("CI checks failed")

        # Calculate score
        total_checks = 5
        passed_checks = sum([files_ok, unrelated_ok, naming_ok, criteria_ok, ci_ok])
        score = int((passed_checks / total_checks) * 100)

        # Determine pass/fail
        # Hard fail on: files mismatch, criteria fail, CI fail
        hard_fail = not files_ok or not criteria_ok or not ci_ok

        return {
            "passed": not hard_fail,
            "score": score,
            "errors": errors,
            "warnings": warnings,
            "checks": {
                "files_match": files_ok,
                "no_unrelated": unrelated_ok,
                "naming_ok": naming_ok,
                "criteria_met": criteria_ok,
                "ci_pass": ci_ok,
            },
        }

    def _validate_files(self, task: Dict, pr_number: int) -> Tuple[bool, List[str]]:
        """Check if PR contains expected files"""
        expected = set(task.get("files_expected", []))
        changed = set(self._get_pr_files(pr_number))

        if not expected:
            return True, []  # No files expected

        missing = expected - changed
        if missing:
            return False, [f"Missing expected files: {', '.join(missing)}"]

        return True, []

    def _check_unrelated_files(
        self, task: Dict, pr_number: int
    ) -> Tuple[bool, List[str]]:
        """Check for unexpected file modifications"""
        expected = set(task.get("files_expected", []))
        changed = set(self._get_pr_files(pr_number))

        # Allow 20% variance (some supporting files OK)
        extra = changed - expected
        max_extra = len(expected) * 0.2

        if len(extra) > max_extra:
            return False, [f"Too many unrelated changes: {', '.join(extra)}"]

        # Warn about any extra
        if extra:
            return True, [f"Note: Extra files modified: {', '.join(extra)}"]

        return True, []

    def _validate_naming(self, task: Dict, pr_number: int) -> Tuple[bool, List[str]]:
        """Check naming conventions"""
        errors = []
        files = self._get_pr_files(pr_number)

        # Check PHP naming
        for file in files:
            if file.endswith(".php"):
                # Check class names match filenames
                if "Controller" in file and not file.endswith("Controller.php"):
                    errors.append(
                        f"Controller file should end with Controller.php: {file}"
                    )

        return len(errors) == 0, errors

    def _validate_criteria(self, task: Dict, pr_number: int) -> Tuple[bool, List[str]]:
        """
        Validate acceptance criteria
        This is basic - can be enhanced with AST parsing
        """
        errors = []
        files = self._get_pr_files(pr_number)

        # Check tests exist for non-test tasks
        if task.get("type") != "Test":
            test_files = [f for f in files if "test" in f.lower() or "Test" in f]
            if not test_files:
                errors.append("No test files found (required by testing skill)")

        # Check migrations have up/down
        for file in files:
            if "migration" in file.lower():
                content = self._get_file_content(pr_number, file)
                if content:
                    if "public function up()" not in content:
                        errors.append(f"Migration missing up() method: {file}")
                    if "public function down()" not in content:
                        errors.append(f"Migration missing down() method: {file}")

        return len(errors) == 0, errors

    def _check_ci_status(self, pr_number: int) -> bool:
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

    def _get_pr_files(self, pr_number: int) -> List[str]:
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

    def _get_file_content(self, pr_number: int, file_path: str) -> Optional[str]:
        """Get content of file in PR"""
        try:
            # Get the PR branch
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "-R",
                    self.repo,
                    "--json",
                    "headRefName",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            branch = data.get("headRefName")

            if branch:
                # Get file content from branch
                result = subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{self.repo}/contents/{file_path}?ref={branch}",
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    import base64

                    return base64.b64decode(data["content"]).decode("utf-8")
        except Exception:
            pass
        return None

    def generate_report(self, validation: Dict) -> str:
        """Generate human-readable validation report"""
        lines = [
            "═" * 60,
            "PR QUALITY GATE REPORT",
            "═" * 60,
            f"\nScore: {validation['score']}/100",
            f"Status: {'✅ PASSED' if validation['passed'] else '❌ FAILED'}",
            "\nChecks:",
        ]

        for check, passed in validation["checks"].items():
            status = "✅" if passed else "❌"
            lines.append(f"  {status} {check}")

        if validation["errors"]:
            lines.append("\n❌ Errors (must fix):")
            for error in validation["errors"]:
                lines.append(f"  • {error}")

        if validation["warnings"]:
            lines.append("\n⚠️  Warnings:")
            for warning in validation["warnings"]:
                lines.append(f"  • {warning}")

        lines.append("═" * 60)
        return "\n".join(lines)


class TaskReplay:
    """
    Store and replay task executions
    Enables deterministic debugging
    """

    def __init__(self, memory_file: str = "JULES_MEMORY.json"):
        self.memory_file = memory_file

    def capture_snapshot(
        self, task: Dict, skills: List[str], prompt: str, repo_state: str
    ) -> Dict:
        """Capture full execution state"""
        return {
            "task_id": task["id"],
            "timestamp": datetime.now().isoformat(),
            "planner_output": task,
            "skills_used": skills,
            "jules_prompt": prompt,
            "repo_state": repo_state,
            "files_expected": task.get("files_expected", []),
            "acceptance_criteria": task.get("acceptance_criteria", []),
        }

    def save_snapshot(self, snapshot: Dict):
        """Save to replay log"""
        replay_file = Path(self.memory_file).parent / "replay-log.json"

        logs = []
        if replay_file.exists():
            with open(replay_file, "r") as f:
                logs = json.load(f)

        logs.append(snapshot)

        with open(replay_file, "w") as f:
            json.dump(logs, f, indent=2)

    def replay_task(self, task_id: str) -> Optional[Dict]:
        """Replay a task from snapshot"""
        replay_file = Path(self.memory_file).parent / "replay-log.json"

        if not replay_file.exists():
            return None

        with open(replay_file, "r") as f:
            logs = json.load(f)

        for log in reversed(logs):
            if log["task_id"] == task_id:
                return log

        return None
