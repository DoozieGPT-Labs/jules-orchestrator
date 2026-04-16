#!/usr/bin/env python3
"""
Plan Validator - Validate execution plans before starting
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Validation result with details"""

    severity: ValidationSeverity
    message: str
    task_id: Optional[str] = None
    field: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class PlanReport:
    """Full validation report"""

    valid: bool
    errors: List[ValidationResult] = field(default_factory=list)
    warnings: List[ValidationResult] = field(default_factory=list)
    info: List[ValidationResult] = field(default_factory=list)

    def add_error(
        self,
        message: str,
        task_id: str = None,
        field: str = None,
        suggestion: str = None,
    ):
        self.errors.append(
            ValidationResult(
                ValidationSeverity.ERROR, message, task_id, field, suggestion
            )
        )

    def add_warning(
        self,
        message: str,
        task_id: str = None,
        field: str = None,
        suggestion: str = None,
    ):
        self.warnings.append(
            ValidationResult(
                ValidationSeverity.WARNING, message, task_id, field, suggestion
            )
        )

    def add_info(self, message: str, task_id: str = None):
        self.info.append(ValidationResult(ValidationSeverity.INFO, message, task_id))

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict:
        return {
            "valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.info),
            "errors": [
                {
                    "message": e.message,
                    "task_id": e.task_id,
                    "field": e.field,
                    "suggestion": e.suggestion,
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "message": w.message,
                    "task_id": w.task_id,
                    "field": w.field,
                    "suggestion": w.suggestion,
                }
                for w in self.warnings
            ],
        }


class PlanValidator:
    """
    Validates execution plans with comprehensive checks:
    - Schema compliance
    - Dependency validity
    - Task completeness
    - Naming conventions
    - Resource limits
    """

    VALID_TASK_TYPES = {"DB", "API", "UI", "Refactor", "Test", "Docs", "Config"}
    VALID_STATUSES = {
        "pending",
        "issue_created",
        "jules_triggered",
        "pr_opened",
        "approved",
        "merging",
        "complete",
        "failed",
        "blocked",
    }

    def __init__(self, max_tasks: int = 20, max_deps_per_task: int = 5):
        self.max_tasks = max_tasks
        self.max_deps_per_task = max_deps_per_task

    def validate(self, plan: Dict) -> PlanReport:
        """
        Run full validation on execution plan
        """
        report = PlanReport(valid=False)

        # Basic structure validation
        self._validate_structure(plan, report)

        if not report.is_valid:
            return report

        tasks = plan.get("tasks", [])
        task_ids = {t.get("id") for t in tasks}

        # Task-level validation
        for task in tasks:
            self._validate_task(task, report)

        # Dependency validation
        self._validate_dependencies(tasks, task_ids, report)

        # Graph validation
        self._validate_graph(tasks, report)

        # Resource limits
        self._validate_limits(tasks, report)

        # Best practices
        self._validate_best_practices(plan, tasks, report)

        report.valid = report.is_valid
        return report

    def _validate_structure(self, plan: Dict, report: PlanReport):
        """Validate basic plan structure"""

        if not isinstance(plan, dict):
            report.add_error("Plan must be a dictionary object")
            return

        # Required fields
        required = ["project_name", "tasks"]
        for field in required:
            if field not in plan:
                report.add_error(f"Missing required field: {field}", field=field)

        # Tasks must be list
        tasks = plan.get("tasks")
        if tasks is not None and not isinstance(tasks, list):
            report.add_error("tasks must be a list", field="tasks")
            return

        # Empty tasks
        if not tasks:
            report.add_warning("No tasks defined in plan")

    def _validate_task(self, task: Dict, report: PlanReport):
        """Validate individual task"""
        task_id = task.get("id", "unknown")

        # Required fields
        if not task.get("id"):
            report.add_error("Task missing id", task_id="unknown", field="id")
            return

        if not task.get("title"):
            report.add_error(
                "Task missing title",
                task_id=task_id,
                field="title",
                suggestion="Add a descriptive title",
            )

        if not task.get("description"):
            report.add_warning(
                "Task missing description",
                task_id=task_id,
                field="description",
                suggestion="Add description for clarity",
            )

        # ID format
        if task.get("id"):
            if not re.match(r"^T\d+$", task.get("id", "")):
                report.add_warning(
                    f"Task ID '{task_id}' should match pattern T<number> (e.g., T1, T2)",
                    task_id=task_id,
                    field="id",
                    suggestion=f"Rename to 'T{task_id}'"
                    if task_id.isdigit()
                    else "Use format like 'T1'",
                )

        # Type validation
        task_type = task.get("type", "").upper()
        if task_type and task_type not in self.VALID_TASK_TYPES:
            report.add_warning(
                f"Unknown task type: {task_type}",
                task_id=task_id,
                field="type",
                suggestion=f"Use one of: {', '.join(self.VALID_TASK_TYPES)}",
            )

        # Status validation
        status = task.get("status", "")
        if status and status not in self.VALID_STATUSES:
            report.add_error(
                f"Invalid status: {status}",
                task_id=task_id,
                field="status",
                suggestion=f"Valid statuses: {', '.join(self.VALID_STATUSES)}",
            )

        # Acceptance criteria
        criteria = task.get("acceptance_criteria", [])
        if not criteria:
            report.add_warning(
                "No acceptance criteria defined",
                task_id=task_id,
                field="acceptance_criteria",
                suggestion="Add at least 2-3 acceptance criteria",
            )
        elif len(criteria) < 2:
            report.add_info("Consider adding more acceptance criteria", task_id=task_id)

        # Expected files
        files = task.get("files_expected", [])
        if not files:
            report.add_warning(
                "No expected files defined",
                task_id=task_id,
                field="files_expected",
                suggestion="List files Jules should create",
            )
        else:
            # Check file paths
            for f in files:
                if ".." in f:
                    report.add_error(
                        f"Invalid file path (contains ..): {f}",
                        task_id=task_id,
                        field="files_expected",
                    )

    def _validate_dependencies(
        self, tasks: List[Dict], task_ids: set, report: PlanReport
    ):
        """Validate task dependencies"""

        for task in tasks:
            task_id = task.get("id", "unknown")
            deps = task.get("dependencies", [])

            # Self-dependency
            if task_id in deps:
                report.add_error(
                    "Task cannot depend on itself",
                    task_id=task_id,
                    field="dependencies",
                    suggestion="Remove self from dependencies",
                )

            # Missing dependencies
            for dep in deps:
                if dep not in task_ids:
                    report.add_error(
                        f"Dependency '{dep}' not found in tasks",
                        task_id=task_id,
                        field=f"dependencies[{dep}]",
                        suggestion=f"Create task '{dep}' or remove dependency",
                    )

            # Too many dependencies
            if len(deps) > self.max_deps_per_task:
                report.add_warning(
                    f"Task has {len(deps)} dependencies (max recommended: {self.max_deps_per_task})",
                    task_id=task_id,
                    field="dependencies",
                    suggestion="Consider breaking into smaller, less coupled tasks",
                )

    def _validate_graph(self, tasks: List[Dict], report: PlanReport):
        """Validate dependency graph (cycles, etc.)"""

        # Build adjacency list
        graph = {}
        task_ids = set()

        for task in tasks:
            tid = task.get("id")
            if tid:
                graph[tid] = task.get("dependencies", [])
                task_ids.add(tid)

        # Check for cycles using DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {t: WHITE for t in task_ids}

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            color[node] = GRAY
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in task_ids:
                    continue

                if color[neighbor] == GRAY:
                    # Cycle found
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

                if color[neighbor] == WHITE:
                    result = dfs(neighbor, path)
                    if result:
                        return result

            path.pop()
            color[node] = BLACK
            return None

        for node in task_ids:
            if color[node] == WHITE:
                cycle = dfs(node, [])
                if cycle:
                    report.add_error(
                        f"Circular dependency detected: {' -> '.join(cycle)}",
                        suggestion="Break the cycle by removing one dependency",
                    )
                    break

        # Check for orphaned tasks (no dependencies, no dependents)
        has_dependents = set()
        for task in tasks:
            for dep in task.get("dependencies", []):
                has_dependents.add(dep)

        for task in tasks:
            tid = task.get("id")
            deps = task.get("dependencies", [])
            if not deps and tid not in has_dependents and len(tasks) > 1:
                report.add_info(
                    f"Task '{tid}' has no dependencies and no tasks depend on it",
                    task_id=tid,
                    suggestion="Consider if this should be a standalone task or connected",
                )

    def _validate_limits(self, tasks: List[Dict], report: PlanReport):
        """Validate resource limits"""

        # Max tasks
        if len(tasks) > self.max_tasks:
            report.add_warning(
                f"Plan has {len(tasks)} tasks (max recommended: {self.max_tasks})",
                suggestion=f"Consider splitting into multiple plans or reducing scope",
            )

        # Total file count
        total_files = sum(len(t.get("files_expected", [])) for t in tasks)
        if total_files > 100:
            report.add_warning(
                f"Plan expects {total_files} files total - very large scope",
                suggestion="Consider breaking into smaller milestones",
            )

    def _validate_best_practices(
        self, plan: Dict, tasks: List[Dict], report: PlanReport
    ):
        """Validate best practices"""

        # Check for test tasks
        has_test_tasks = any(
            t.get("type", "").upper() == "TEST" or "test" in t.get("title", "").lower()
            for t in tasks
        )

        if not has_test_tasks and len(tasks) > 2:
            report.add_warning(
                "No test tasks defined - consider adding test coverage",
                suggestion="Add task with type='Test' for critical features",
            )

        # Check for DB migrations before dependent tasks
        db_tasks = [t for t in tasks if t.get("type", "").upper() == "DB"]
        for db_task in db_tasks:
            deps = db_task.get("dependencies", [])
            if deps:
                report.add_info(
                    f"DB task '{db_task['id']}' has dependencies - ensure migrations run first",
                    task_id=db_task["id"],
                    suggestion="DB migrations should typically be early in the dependency chain",
                )

        # Check project name format
        project_name = plan.get("project_name", "")
        if project_name:
            if " " in project_name:
                report.add_warning(
                    "Project name contains spaces - consider using kebab-case",
                    suggestion=f"Use '{project_name.replace(' ', '-').lower()}'",
                )
            if not re.match(r"^[a-z0-9-]+$", project_name.lower()):
                report.add_info(
                    "Project name should use lowercase letters, numbers, and hyphens only",
                    suggestion="Use kebab-case: my-awesome-project",
                )

    def fix_auto(self, plan: Dict) -> Dict:
        """
        Auto-fix common issues
        """
        fixed = json.loads(json.dumps(plan))  # Deep copy

        tasks = fixed.get("tasks", [])
        task_ids = {t.get("id") for t in tasks}

        for task in tasks:
            # Fix task ID format
            task_id = task.get("id", "")
            if task_id and not re.match(r"^T\d+$", task_id):
                # Try to extract number
                numbers = re.findall(r"\d+", task_id)
                if numbers:
                    task["id"] = f"T{numbers[0]}"

            # Remove invalid dependencies
            deps = task.get("dependencies", [])
            task["dependencies"] = [d for d in deps if d in task_ids and d != task_id]

            # Set default status
            if not task.get("status"):
                task["status"] = "pending"

            # Normalize type
            if task.get("type"):
                task["type"] = task["type"].upper()

        # Normalize project name
        if fixed.get("project_name"):
            fixed["project_name"] = fixed["project_name"].lower().replace(" ", "-")

        return fixed

    def generate_plan_summary(self, plan: Dict) -> str:
        """Generate human-readable plan summary"""
        tasks = plan.get("tasks", [])

        lines = [
            "=" * 60,
            "PLAN VALIDATION SUMMARY",
            "=" * 60,
            "",
            f"Project: {plan.get('project_name', 'Unnamed')}",
            f"Total Tasks: {len(tasks)}",
            "",
            "Task Breakdown:",
        ]

        # Count by type
        by_type = {}
        for task in tasks:
            t = task.get("type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1

        for task_type, count in sorted(by_type.items()):
            lines.append(f"  {task_type}: {count}")

        # Dependency stats
        deps_count = sum(len(t.get("dependencies", [])) for t in tasks)
        lines.extend(
            [
                "",
                f"Total Dependencies: {deps_count}",
                f"Avg Dependencies per Task: {deps_count / max(len(tasks), 1):.1f}",
                "",
            ]
        )

        # Critical path estimation
        from .dependency_resolver import DependencyResolver

        try:
            resolver = DependencyResolver(tasks)
            levels = resolver.topological_sort_levels()
            lines.append(f"Execution Levels: {len(levels)}")
            lines.append(
                f"Max Parallel Tasks: {max(len(l) for l in levels) if levels else 0}"
            )
        except Exception:
            lines.append("(Could not calculate execution levels)")

        lines.append("=" * 60)

        return "\n".join(lines)


def validate_plan_file(filepath: str) -> PlanReport:
    """Validate a plan file"""
    try:
        with open(filepath, "r") as f:
            plan = json.load(f)

        validator = PlanValidator()
        return validator.validate(plan)
    except json.JSONDecodeError as e:
        report = PlanReport(valid=False)
        report.add_error(f"Invalid JSON: {e}")
        return report
    except FileNotFoundError:
        report = PlanReport(valid=False)
        report.add_error(f"File not found: {filepath}")
        return report


if __name__ == "__main__":
    # Test
    import sys

    if len(sys.argv) > 1:
        report = validate_plan_file(sys.argv[1])
    else:
        # Test with sample
        sample = {
            "project_name": "Test Project",
            "tasks": [
                {"id": "T1", "title": "Setup", "type": "Config", "dependencies": []},
                {"id": "T2", "title": "DB", "type": "DB", "dependencies": ["T1"]},
                {"id": "T3", "title": "API", "type": "API", "dependencies": ["T2"]},
            ],
        }
        validator = PlanValidator()
        report = validator.validate(sample)
        print(validator.generate_plan_summary(sample))

    print(f"\nValid: {report.is_valid}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")
    print(f"Info: {len(report.info)}")

    if report.errors:
        print("\nErrors:")
        for e in report.errors:
            print(f"  - {e.message}")

    if report.warnings:
        print("\nWarnings:")
        for w in report.warnings:
            print(f"  - {w.message}")
