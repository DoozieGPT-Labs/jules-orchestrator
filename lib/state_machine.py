#!/usr/bin/env python3
"""
State Machine - Enforced state transitions for tasks
"""

from typing import Dict, List, Optional, Set, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class TaskState(Enum):
    """Valid task states"""

    PENDING = "pending"
    ISSUE_CREATED = "issue_created"
    JULES_TRIGGERED = "jules_triggered"
    PR_OPENED = "pr_opened"
    APPROVED = "approved"
    MERGING = "merging"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class StateTransition:
    """Record of a state transition"""

    from_state: str
    to_state: str
    timestamp: str
    reason: Optional[str] = None


class StateMachine:
    """
    Enforced state machine for task lifecycle

    Valid transitions:
    - pending → issue_created
    - issue_created → jules_triggered, failed
    - jules_triggered → pr_opened, failed
    - pr_opened → approved, failed
    - approved → merging, failed
    - merging → complete, failed
    - failed → issue_created (retry), blocked
    - blocked → issue_created (manual retry)
    """

    VALID_TRANSITIONS: Dict[str, Set[str]] = {
        "pending": {"issue_created"},
        "issue_created": {"jules_triggered", "failed"},
        "jules_triggered": {"pr_opened", "failed"},
        "pr_opened": {"approved", "failed"},
        "approved": {"merging", "failed"},
        "merging": {"complete", "failed"},
        "failed": {"issue_created", "blocked"},
        "blocked": {"issue_created"},
        "complete": set(),  # Terminal state
    }

    TERMINAL_STATES = {"complete", "blocked"}

    def __init__(self):
        self._transition_listeners: List[Callable] = []
        self._audit_log: List[Dict] = []

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """Check if transition is valid"""
        if from_state not in self.VALID_TRANSITIONS:
            return False
        return to_state in self.VALID_TRANSITIONS[from_state]

    def transition(self, task: Dict, new_state: str, reason: str = None) -> bool:
        """
        Attempt state transition

        Returns True if successful, False if invalid
        """
        current_state = task.get("status", "pending")
        task_id = task.get("id", "unknown")

        # Check if transition is valid
        if not self.can_transition(current_state, new_state):
            raise InvalidStateTransition(
                f"Cannot transition {task_id}: {current_state} → {new_state}. "
                f"Valid transitions from {current_state}: {self.VALID_TRANSITIONS.get(current_state, set())}"
            )

        # Record transition
        transition = StateTransition(
            from_state=current_state,
            to_state=new_state,
            timestamp=datetime.now().isoformat(),
            reason=reason,
        )

        # Initialize state history if needed
        if "state_history" not in task:
            task["state_history"] = []

        task["state_history"].append(
            {
                "from": transition.from_state,
                "to": transition.to_state,
                "at": transition.timestamp,
                "reason": reason,
            }
        )

        # Update state
        task["status"] = new_state
        task["last_state_change"] = transition.timestamp

        # Notify listeners
        for listener in self._transition_listeners:
            try:
                listener(task, transition)
            except Exception:
                pass

        return True

    def force_transition(self, task: Dict, new_state: str, reason: str = None):
        """
        Force a transition (bypass validation) - use with caution
        """
        current_state = task.get("status", "pending")

        if "state_history" not in task:
            task["state_history"] = []

        task["state_history"].append(
            {
                "from": current_state,
                "to": new_state,
                "at": datetime.now().isoformat(),
                "reason": reason or "FORCED",
                "forced": True,
            }
        )

        task["status"] = new_state
        task["last_state_change"] = datetime.now().isoformat()

    def get_valid_transitions(self, state: str) -> Set[str]:
        """Get valid next states from current state"""
        return self.VALID_TRANSITIONS.get(state, set())

    def is_terminal(self, state: str) -> bool:
        """Check if state is terminal"""
        return state in self.TERMINAL_STATES

    def add_listener(self, callback: Callable):
        """Add transition listener"""
        self._transition_listeners.append(callback)

    def validate_task_history(self, task: Dict) -> List[str]:
        """Validate task's state history for integrity"""
        errors = []
        history = task.get("state_history", [])

        if not history:
            return errors

        # Check first transition is from pending or matches current
        if history and history[0].get("from") != "pending":
            errors.append(
                f"Task {task['id']}: State history doesn't start from pending"
            )

        # Check all transitions are valid
        for i, entry in enumerate(history):
            from_state = entry.get("from")
            to_state = entry.get("to")

            if not self.can_transition(from_state, to_state):
                errors.append(
                    f"Task {task['id']}: Invalid transition at step {i}: "
                    f"{from_state} → {to_state}"
                )

            # Check continuity
            if i > 0:
                prev_to = history[i - 1].get("to")
                if from_state != prev_to:
                    errors.append(
                        f"Task {task['id']}: Discontinuity at step {i}: "
                        f"expected from={prev_to}, got {from_state}"
                    )

        return errors

    def get_state_metrics(self, tasks: List[Dict]) -> Dict:
        """Get metrics about state distribution"""
        counts = {}
        for state in TaskState:
            counts[state.value] = 0

        for task in tasks:
            status = task.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1

        return {
            "total": len(tasks),
            "by_state": counts,
            "terminal": sum(counts.get(s, 0) for s in self.TERMINAL_STATES),
            "in_progress": len(tasks)
            - sum(counts.get(s, 0) for s in self.TERMINAL_STATES),
        }

    def detect_stalled_tasks(
        self, tasks: List[Dict], max_age_minutes: int = 60
    ) -> List[Dict]:
        """Detect tasks that may be stalled"""
        stalled = []

        for task in tasks:
            if self.is_terminal(task.get("status", "")):
                continue

            last_change = task.get("last_state_change")
            if not last_change:
                stalled.append(task)
                continue

            try:
                from datetime import datetime

                last = datetime.fromisoformat(last_change)
                age = (datetime.now() - last).total_seconds() / 60

                if age > max_age_minutes:
                    stalled.append({**task, "stalled_for_minutes": int(age)})
            except Exception:
                pass

        return stalled


class InvalidStateTransition(Exception):
    """Raised when invalid state transition attempted"""

    pass


class StateRecovery:
    """Recovery utilities for stuck/blocked tasks"""

    RECOVERY_PATHS = {
        "blocked": ["issue_created"],
        "failed": ["issue_created"],
        "merging": ["complete", "approved"],  # Check if actually merged
        "jules_triggered": ["pr_opened", "issue_created"],
        "pr_opened": ["approved", "issue_created"],
    }

    def __init__(self, state_machine: StateMachine):
        self.sm = state_machine

    def can_recover(self, task: Dict) -> bool:
        """Check if task can be recovered"""
        state = task.get("status", "")
        return state in self.RECOVERY_PATHS

    def get_recovery_options(self, task: Dict) -> List[Dict]:
        """Get available recovery options for task"""
        state = task.get("status", "")
        options = []

        if state not in self.RECOVERY_PATHS:
            return options

        for target in self.RECOVERY_PATHS[state]:
            if target == "issue_created":
                options.append(
                    {
                        "action": "retry",
                        "target_state": "issue_created",
                        "description": "Create new issue and retry",
                        "reset_retry_count": False,
                    }
                )
            elif target == "complete":
                options.append(
                    {
                        "action": "verify_merge",
                        "target_state": "complete",
                        "description": "Check if PR was actually merged",
                    }
                )
            elif target == "approved":
                options.append(
                    {
                        "action": "revalidate",
                        "target_state": "approved",
                        "description": "Re-run validation and approval",
                    }
                )
            elif target == "pr_opened":
                options.append(
                    {
                        "action": "find_pr",
                        "target_state": "pr_opened",
                        "description": "Search for existing PR",
                    }
                )

        return options

    def apply_recovery(self, task: Dict, option: Dict) -> bool:
        """Apply recovery action to task"""
        action = option.get("action")
        target = option.get("target_state")

        if action == "retry":
            # Reset for retry
            task["retry_count"] = task.get("retry_count", 0)
            self.sm.transition(task, target, reason="Manual recovery retry")
            return True

        elif action == "verify_merge":
            # External code should check PR status
            self.sm.transition(task, target, reason="Recovery: verified merge")
            return True

        elif action == "revalidate":
            self.sm.transition(task, target, reason="Recovery: revalidated")
            return True

        elif action == "find_pr":
            self.sm.transition(task, target, reason="Recovery: PR found")
            return True

        return False


def generate_state_diagram() -> str:
    """Generate Mermaid state diagram"""
    lines = [
        "stateDiagram-v2",
        "    [*] --> pending: Initialize",
        "    pending --> issue_created: Create Issue",
        "    issue_created --> jules_triggered: Trigger Jules",
        "    issue_created --> failed: Jules Error",
        "    jules_triggered --> pr_opened: PR Created",
        "    jules_triggered --> failed: Timeout",
        "    pr_opened --> approved: Validation Pass",
        "    pr_opened --> failed: Validation Fail",
        "    approved --> merging: Merge Start",
        "    approved --> failed: Merge Error",
        "    merging --> complete: Merge Success",
        "    merging --> failed: Merge Fail",
        "    failed --> issue_created: Retry",
        "    failed --> blocked: Max Retries",
        "    blocked --> issue_created: Manual Retry",
        "    complete --> [*]: Done",
        "    blocked --> [*]: Abandon",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    # Test
    sm = StateMachine()

    task = {"id": "T1", "status": "pending"}

    print("Testing state transitions...")

    # Valid transition
    sm.transition(task, "issue_created", "Test transition")
    print(f"T1: {task['status']}")
    print(f"History: {task['state_history']}")

    # Invalid transition
    try:
        sm.transition(task, "complete")
    except InvalidStateTransition as e:
        print(f"\nExpected error: {e}")

    # Valid
    sm.transition(task, "jules_triggered")
    sm.transition(task, "pr_opened")
    print(f"\nT1 after valid transitions: {task['status']}")

    # Generate diagram
    print("\n" + "=" * 60)
    print("State Diagram (Mermaid):")
    print("=" * 60)
    print(generate_state_diagram())
