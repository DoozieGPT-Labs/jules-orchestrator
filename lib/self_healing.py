#!/usr/bin/env python3
"""
SelfHealingEngine - Automatic recovery and healing mechanisms
"""

import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class HealingActionType(Enum):
    """Types of healing actions"""

    RETRY = "retry"
    ROLLBACK = "rollback"
    SKIP = "skip"
    MANUAL_ESCALATION = "manual_escalation"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"
    CACHE_INVALIDATION = "cache_invalidation"
    DEPENDENCY_REORDER = "dependency_reorder"


@dataclass
class HealingAction:
    """A healing action to take"""

    action_type: HealingActionType
    task_id: Optional[str]
    reason: str
    confidence: float
    expected_outcome: str
    rollback_possible: bool
    metadata: Dict[str, Any]


@dataclass
class FailurePattern:
    """Recognized failure pattern"""

    pattern_id: str
    name: str
    description: str
    symptoms: List[str]
    root_causes: List[str]
    healing_actions: List[HealingActionType]
    success_rate: float


class FailurePatternLibrary:
    """Library of recognized failure patterns"""

    def __init__(self):
        self.patterns: Dict[str, FailurePattern] = {}
        self._init_default_patterns()

    def _init_default_patterns(self):
        """Initialize default failure patterns"""

        # Pattern 1: API Rate Limiting
        self.patterns["api_rate_limit"] = FailurePattern(
            pattern_id="api_rate_limit",
            name="GitHub API Rate Limiting",
            description="Hit GitHub API rate limit",
            symptoms=["rate limit", "403", "too many requests"],
            root_causes=["Excessive API calls", "No rate limit handling"],
            healing_actions=[
                HealingActionType.CIRCUIT_BREAKER_RESET,
                HealingActionType.RETRY,
            ],
            success_rate=0.85,
        )

        # Pattern 2: Network Timeout
        self.patterns["network_timeout"] = FailurePattern(
            pattern_id="network_timeout",
            name="Network Timeout",
            description="Network operation timed out",
            symptoms=["timeout", "connection refused", "no response"],
            root_causes=["Network instability", "Slow API response"],
            healing_actions=[
                HealingActionType.RETRY,
                HealingActionType.CACHE_INVALIDATION,
            ],
            success_rate=0.70,
        )

        # Pattern 3: Validation Failure
        self.patterns["validation_failure"] = FailurePattern(
            pattern_id="validation_failure",
            name="Quality Gate Failure",
            description="PR failed validation checks",
            symptoms=["validation failed", "quality gate", "missing files"],
            root_causes=["Incomplete implementation", "Missing tests"],
            healing_actions=[
                HealingActionType.MANUAL_ESCALATION,
            ],
            success_rate=0.40,
        )

        # Pattern 4: Stale Task
        self.patterns["stale_task"] = FailurePattern(
            pattern_id="stale_task",
            name="Task Stuck in State",
            description="Task not progressing for extended time",
            symptoms=["stuck", "no progress", "orphaned"],
            root_causes=["Lost PR tracking", "Jules not processing"],
            healing_actions=[
                HealingActionType.CACHE_INVALIDATION,
                HealingActionType.RETRY,
            ],
            success_rate=0.75,
        )

        # Pattern 5: Dependency Failure
        self.patterns["dependency_failure"] = FailurePattern(
            pattern_id="dependency_failure",
            name="Dependency Task Failed",
            description="Required dependency task failed",
            symptoms=["dependency failed", "waiting for"],
            root_causes=["Upstream failure", "Circular dependency"],
            healing_actions=[
                HealingActionType.DEPENDENCY_REORDER,
                HealingActionType.MANUAL_ESCALATION,
            ],
            success_rate=0.50,
        )

        # Pattern 6: Merge Conflict
        self.patterns["merge_conflict"] = FailurePattern(
            pattern_id="merge_conflict",
            name="Merge Conflict",
            description="PR has merge conflicts",
            symptoms=["merge conflict", "cannot merge"],
            root_causes=["Concurrent changes", "Out of date branch"],
            healing_actions=[
                HealingActionType.ROLLBACK,
                HealingActionType.RETRY,
            ],
            success_rate=0.60,
        )

    def match_pattern(self, failure_reason: str) -> List[FailurePattern]:
        """Match failure reason to known patterns"""
        matched = []
        reason_lower = failure_reason.lower()

        for pattern in self.patterns.values():
            for symptom in pattern.symptoms:
                if symptom.lower() in reason_lower:
                    matched.append(pattern)
                    break

        return matched

    def get_pattern(self, pattern_id: str) -> Optional[FailurePattern]:
        """Get pattern by ID"""
        return self.patterns.get(pattern_id)


class SelfHealingEngine:
    """
    Self-healing engine for automatic failure recovery

    Analyzes failures and applies healing actions based on:
    - Recognized failure patterns
    - Historical success rates
    - Current system state
    """

    def __init__(self, github_client=None, state_machine=None, audit_log=None):
        self.github = github_client
        self.state_machine = state_machine
        self.audit = audit_log
        self.logger = logging.getLogger("self-healing")

        self.pattern_library = FailurePatternLibrary()
        self.healing_history: List[Dict] = []

        # Healing action handlers
        self.action_handlers: Dict[HealingActionType, Callable] = {
            HealingActionType.RETRY: self._handle_retry,
            HealingActionType.ROLLBACK: self._handle_rollback,
            HealingActionType.SKIP: self._handle_skip,
            HealingActionType.MANUAL_ESCALATION: self._handle_escalation,
            HealingActionType.CIRCUIT_BREAKER_RESET: self._handle_circuit_reset,
            HealingActionType.CACHE_INVALIDATION: self._handle_cache_invalidation,
            HealingActionType.DEPENDENCY_REORDER: self._handle_dependency_reorder,
        }

    def analyze_failure(
        self, task: Dict, failure_reason: str
    ) -> Optional[HealingAction]:
        """Analyze failure and suggest healing action"""

        # Match failure to patterns
        patterns = self.pattern_library.match_pattern(failure_reason)

        if not patterns:
            return None

        # Sort by success rate
        patterns.sort(key=lambda p: p.success_rate, reverse=True)
        best_pattern = patterns[0]

        # Create healing action
        if best_pattern.healing_actions:
            action_type = best_pattern.healing_actions[0]

            action = HealingAction(
                action_type=action_type,
                task_id=task.get("id"),
                reason=f"Matched pattern: {best_pattern.name}",
                confidence=best_pattern.success_rate,
                expected_outcome=self._get_expected_outcome(action_type),
                rollback_possible=action_type != HealingActionType.MANUAL_ESCALATION,
                metadata={
                    "pattern_id": best_pattern.pattern_id,
                    "failure_reason": failure_reason,
                },
            )

            return action

        return None

    def _get_expected_outcome(self, action_type: HealingActionType) -> str:
        """Get expected outcome for healing action"""
        outcomes = {
            HealingActionType.RETRY: "Task succeeds on retry",
            HealingActionType.ROLLBACK: "Task reset to previous state",
            HealingActionType.SKIP: "Task skipped, dependencies updated",
            HealingActionType.MANUAL_ESCALATION: "Human intervention required",
            HealingActionType.CIRCUIT_BREAKER_RESET: "API calls resume normally",
            HealingActionType.CACHE_INVALIDATION: "Fresh data retrieved",
            HealingActionType.DEPENDENCY_REORDER: "Tasks rescheduled",
        }
        return outcomes.get(action_type, "Unknown")

    def execute_healing(self, task: Dict, action: HealingAction, memory: Dict) -> bool:
        """Execute healing action"""

        self.logger.info(
            f"Executing healing action {action.action_type.value} "
            f"for task {action.task_id}"
        )

        # Record attempt
        self.healing_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "task_id": action.task_id,
                "action": action.action_type.value,
                "reason": action.reason,
                "confidence": action.confidence,
            }
        )

        # Execute handler
        handler = self.action_handlers.get(action.action_type)
        if handler:
            try:
                success = handler(task, action, memory)

                if success:
                    self.logger.info(
                        f"Healing action succeeded for task {action.task_id}"
                    )
                    if self.audit:
                        self.audit.log_event(
                            "healing_success",
                            action.task_id,
                            {
                                "action": action.action_type.value,
                                "reason": action.reason,
                            },
                        )
                else:
                    self.logger.warning(
                        f"Healing action failed for task {action.task_id}"
                    )

                return success
            except Exception as e:
                self.logger.error(f"Healing action error: {e}")
                return False

        return False

    def _handle_retry(self, task: Dict, action: HealingAction, memory: Dict) -> bool:
        """Handle retry healing"""
        # Reset task for retry
        retry_count = task.get("retry_count", 0)
        task["retry_count"] = retry_count + 1
        task["failure_reason"] = None

        # Transition to pending if blocked
        if task.get("status") == "blocked":
            if self.state_machine:
                self.state_machine.force_transition(
                    task, "pending", "Self-healing retry"
                )

        return True

    def _handle_rollback(self, task: Dict, action: HealingAction, memory: Dict) -> bool:
        """Handle rollback healing"""
        # Reset task to initial state
        task["status"] = "pending"
        task["issue_id"] = None
        task["pr_id"] = None
        task["failure_reason"] = None
        task["retry_count"] = task.get("retry_count", 0)

        if self.state_machine:
            task["state_history"] = []

        return True

    def _handle_skip(self, task: Dict, action: HealingAction, memory: Dict) -> bool:
        """Handle skip healing"""
        # Mark task as complete with note
        task["status"] = "complete"
        task["skipped"] = True
        task["skip_reason"] = action.reason

        # Update dependent tasks
        for t in memory.get("tasks", []):
            if task["id"] in t.get("dependencies", []):
                # Remove this dependency
                t["dependencies"] = [d for d in t["dependencies"] if d != task["id"]]

        return True

    def _handle_escalation(
        self, task: Dict, action: HealingAction, memory: Dict
    ) -> bool:
        """Handle manual escalation"""
        # Create escalation issue/alert
        task["escalated"] = True
        task["escalation_reason"] = action.reason
        task["status"] = "blocked"

        # Log for manual review
        self.logger.error(
            f"Task {task['id']} escalated for manual review: {action.reason}"
        )

        return True

    def _handle_circuit_reset(
        self, task: Dict, action: HealingAction, memory: Dict
    ) -> bool:
        """Handle circuit breaker reset"""
        try:
            from circuit_breaker import get_circuit_breaker, GITHUB_CIRCUIT

            breaker = get_circuit_breaker(GITHUB_CIRCUIT)
            if breaker:
                breaker.force_close("Self-healing recovery")
                return True
        except Exception as e:
            self.logger.error(f"Failed to reset circuit breaker: {e}")

        return False

    def _handle_cache_invalidation(
        self, task: Dict, action: HealingAction, memory: Dict
    ) -> bool:
        """Handle cache invalidation"""
        # This would integrate with cache manager
        self.logger.info("Cache invalidated for self-healing")
        return True

    def _handle_dependency_reorder(
        self, task: Dict, action: HealingAction, memory: Dict
    ) -> bool:
        """Handle dependency reordering"""
        # Remove failed dependency and reschedule
        failed_deps = task.get("dependencies", [])

        # Find failed dependencies and remove them
        for dep_id in failed_deps[:]:
            dep = next((t for t in memory.get("tasks", []) if t["id"] == dep_id), None)
            if dep and dep.get("status") == "failed":
                task["dependencies"] = [d for d in task["dependencies"] if d != dep_id]
                task["removed_dependencies"] = task.get("removed_dependencies", []) + [
                    dep_id
                ]

        return True

    def should_attempt_healing(self, task: Dict) -> bool:
        """Determine if task should be healed"""
        # Don't heal tasks that are:
        # - Already complete
        # - Blocked (wait for manual review)
        # - Escalated

        status = task.get("status", "")
        if status in ["complete", "blocked"]:
            return False

        if task.get("escalated"):
            return False

        # Check retry count
        if task.get("retry_count", 0) >= 3:
            return False

        return True

    def get_healing_stats(self) -> Dict:
        """Get healing statistics"""
        total = len(self.healing_history)
        if total == 0:
            return {"total_attempts": 0}

        by_action = {}
        for h in self.healing_history:
            action = h.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1

        return {
            "total_attempts": total,
            "by_action": by_action,
            "recent": list(self.healing_history)[-10:],
        }

    def generate_healing_report(self) -> str:
        """Generate human-readable healing report"""
        stats = self.get_healing_stats()

        lines = [
            "=" * 60,
            "SELF-HEALING REPORT",
            "=" * 60,
            f"\nTotal Healing Attempts: {stats['total_attempts']}",
            "\nBy Action Type:",
        ]

        for action, count in stats.get("by_action", {}).items():
            lines.append(f"  {action}: {count}")

        lines.extend(
            [
                "\n" + "=" * 60,
                "RECOGNIZED PATTERNS:",
                "=" * 60,
            ]
        )

        for pattern_id, pattern in self.pattern_library.patterns.items():
            lines.append(f"\n  {pattern.name}")
            lines.append(f"    Success Rate: {pattern.success_rate:.1%}")
            lines.append(f"    Actions: {[a.value for a in pattern.healing_actions]}")

        return "\n".join(lines)


def should_heal_task(task: Dict, failure_reason: str) -> bool:
    """Convenience function to check if task should be healed"""
    engine = SelfHealingEngine()

    if not engine.should_attempt_healing(task):
        return False

    action = engine.analyze_failure(task, failure_reason)
    return action is not None and action.confidence > 0.5


if __name__ == "__main__":
    # Test
    engine = SelfHealingEngine()

    test_task = {
        "id": "T1",
        "status": "failed",
        "retry_count": 1,
        "failure_reason": "API rate limit exceeded",
    }

    # Analyze failure
    action = engine.analyze_failure(test_task, test_task["failure_reason"])

    if action:
        print(f"Detected healing action: {action.action_type.value}")
        print(f"Confidence: {action.confidence:.1%}")
        print(f"Expected outcome: {action.expected_outcome}")

        # Execute healing
        success = engine.execute_healing(test_task, action, {"tasks": [test_task]})
        print(f"Healing {'succeeded' if success else 'failed'}")

    print("\nHealing Stats:")
    print(engine.get_healing_stats())
