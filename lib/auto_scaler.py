#!/usr/bin/env python3
"""
AutoScaler - Dynamic scaling for parallel task execution

Automatically adjusts concurrency based on:
- GitHub API rate limits
- System resources
- Historical execution patterns
- Task queue depth
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque
from datetime import datetime
import threading


@dataclass
class ScalingMetrics:
    """Metrics for scaling decisions"""

    api_rate_limit_remaining: int
    api_rate_limit_reset: int
    cpu_percent: float
    memory_percent: float
    active_tasks: int
    queued_tasks: int
    completed_last_minute: int
    avg_task_duration: float


@dataclass
class ScalingDecision:
    """Scaling decision result"""

    timestamp: str
    current_concurrency: int
    recommended_concurrency: int
    reason: str
    metrics: ScalingMetrics


class AutoScaler:
    """
    Auto-scaler for parallel task execution

    Monitors various metrics and dynamically adjusts concurrency:
    - Respects GitHub API rate limits
    - Prevents resource exhaustion
    - Optimizes throughput based on historical patterns
    """

    def __init__(
        self,
        min_concurrency: int = 1,
        max_concurrency: int = 10,
        github_client=None,
        metrics_collector=None,
    ):
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.github = github_client
        self.metrics = metrics_collector
        self.logger = logging.getLogger("auto-scaler")

        # Current state
        self.current_concurrency = min_concurrency
        self.target_concurrency = min_concurrency

        # History for trend analysis
        self.execution_history = deque(maxlen=100)
        self.rate_limit_history = deque(maxlen=50)

        # Scaling thresholds
        self.scale_up_threshold = 0.8  # Scale up when 80% throughput
        self.scale_down_threshold = 0.3  # Scale down when 30% throughput
        self.rate_limit_buffer = 100  # Keep 100 requests buffer

        # Cooldown period
        self.last_scale_time = 0
        self.scale_cooldown = 60  # seconds

        self._lock = threading.Lock()

    def get_current_concurrency(self) -> int:
        """Get current concurrency level"""
        with self._lock:
            return self.current_concurrency

    def evaluate_and_scale(self) -> Optional[ScalingDecision]:
        """Evaluate metrics and make scaling decision"""
        # Check cooldown
        if time.time() - self.last_scale_time < self.scale_cooldown:
            return None

        # Collect metrics
        metrics = self._collect_metrics()
        if not metrics:
            return None

        # Make decision
        decision = self._make_scaling_decision(metrics)

        # Apply decision
        if decision.recommended_concurrency != self.current_concurrency:
            self._apply_scaling(decision)

        return decision

    def _collect_metrics(self) -> Optional[ScalingMetrics]:
        """Collect current metrics"""
        try:
            # API rate limit
            api_remaining = 5000  # Default
            api_reset = 3600
            if self.github:
                try:
                    # This would need to be implemented in GitHubClient
                    rate_info = self._get_rate_limit_info()
                    if rate_info:
                        api_remaining = rate_info.get("remaining", 5000)
                        api_reset = rate_info.get("reset_in", 3600)
                except Exception:
                    pass

            # System resources
            cpu_percent = self._get_cpu_percent()
            memory_percent = self._get_memory_percent()

            # Task metrics
            active = self._get_active_tasks()
            queued = self._get_queued_tasks()
            completed = self._get_completed_last_minute()
            avg_duration = self._get_avg_duration()

            return ScalingMetrics(
                api_rate_limit_remaining=api_remaining,
                api_rate_limit_reset=api_reset,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                active_tasks=active,
                queued_tasks=queued,
                completed_last_minute=completed,
                avg_task_duration=avg_duration,
            )

        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")
            return None

    def _get_rate_limit_info(self) -> Dict:
        """Get GitHub API rate limit info"""
        # This would call GitHub API
        # For now, return dummy data
        return {"remaining": 4500, "reset_in": 3000}

    def _get_cpu_percent(self) -> float:
        """Get CPU usage percentage"""
        try:
            import psutil

            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            return 0.0

    def _get_memory_percent(self) -> float:
        """Get memory usage percentage"""
        try:
            import psutil

            return psutil.virtual_memory().percent
        except ImportError:
            return 0.0

    def _get_active_tasks(self) -> int:
        """Get number of currently active tasks"""
        # Would integrate with task executor
        return 0

    def _get_queued_tasks(self) -> int:
        """Get number of queued tasks"""
        # Would integrate with task queue
        return 0

    def _get_completed_last_minute(self) -> int:
        """Get number of tasks completed in last minute"""
        cutoff = time.time() - 60
        return sum(1 for t in self.execution_history if t > cutoff)

    def _get_avg_duration(self) -> float:
        """Get average task duration"""
        if not self.execution_history:
            return 300.0
        return sum(self.execution_history) / len(self.execution_history)

    def _make_scaling_decision(self, metrics: ScalingMetrics) -> ScalingDecision:
        """Make scaling decision based on metrics"""
        reasons = []

        # Calculate throughput ratio
        throughput_ratio = self._calculate_throughput_ratio(metrics)

        # Check rate limits
        if metrics.api_rate_limit_remaining < self.rate_limit_buffer:
            # Scale down to conserve API calls
            new_concurrency = max(self.min_concurrency, self.current_concurrency - 2)
            reasons.append(
                f"Rate limit low ({metrics.api_rate_limit_remaining} remaining), "
                "scaling down"
            )

        # Check resource usage
        elif metrics.cpu_percent > 80 or metrics.memory_percent > 85:
            # Scale down to prevent resource exhaustion
            new_concurrency = max(self.min_concurrency, self.current_concurrency - 1)
            reasons.append(
                f"Resource pressure (CPU: {metrics.cpu_percent}%, "
                f"Memory: {metrics.memory_percent}%), scaling down"
            )

        # Check if we should scale up
        elif throughput_ratio > self.scale_up_threshold:
            # Scale up if we have capacity
            new_concurrency = min(self.max_concurrency, self.current_concurrency + 1)
            reasons.append(f"High throughput ({throughput_ratio:.1%}), scaling up")

        # Check if we should scale down
        elif throughput_ratio < self.scale_down_threshold:
            # Scale down if underutilized
            new_concurrency = max(self.min_concurrency, self.current_concurrency - 1)
            reasons.append(f"Low throughput ({throughput_ratio:.1%}), scaling down")

        else:
            # No change needed
            new_concurrency = self.current_concurrency
            reasons.append("Current concurrency optimal")

        # Ensure within bounds
        new_concurrency = max(
            self.min_concurrency, min(self.max_concurrency, new_concurrency)
        )

        reason_str = "; ".join(reasons) if reasons else "No change needed"

        return ScalingDecision(
            timestamp=datetime.now().isoformat(),
            current_concurrency=self.current_concurrency,
            recommended_concurrency=new_concurrency,
            reason=reason_str,
            metrics=metrics,
        )

    def _calculate_throughput_ratio(self, metrics: ScalingMetrics) -> float:
        """Calculate throughput ratio (actual / potential)"""
        if self.current_concurrency == 0:
            return 0.0

        # Theoretical max tasks per minute at current concurrency
        if metrics.avg_task_duration > 0:
            theoretical_max = (
                60 / metrics.avg_task_duration
            ) * self.current_concurrency
        else:
            theoretical_max = self.current_concurrency

        if theoretical_max == 0:
            return 0.0

        actual = metrics.completed_last_minute
        return min(actual / theoretical_max, 1.0)

    def _apply_scaling(self, decision: ScalingDecision):
        """Apply scaling decision"""
        with self._lock:
            old_concurrency = self.current_concurrency
            self.current_concurrency = decision.recommended_concurrency
            self.last_scale_time = time.time()

        if old_concurrency != self.current_concurrency:
            self.logger.info(
                f"Scaled from {old_concurrency} to {self.current_concurrency}: "
                f"{decision.reason}"
            )

    def record_task_completion(self, duration_seconds: float):
        """Record task completion for historical analysis"""
        self.execution_history.append(duration_seconds)

    def get_scaling_history(self, limit: int = 20) -> List[Dict]:
        """Get recent scaling decisions"""
        # Would be stored persistently in real implementation
        return []

    def get_recommendation(self) -> str:
        """Get human-readable scaling recommendation"""
        metrics = self._collect_metrics()
        if not metrics:
            return "Unable to collect metrics for recommendation"

        decision = self._make_scaling_decision(metrics)

        return (
            f"Current concurrency: {decision.current_concurrency}\n"
            f"Recommended: {decision.recommended_concurrency}\n"
            f"Reason: {decision.reason}\n"
            f"\nMetrics:\n"
            f"  API remaining: {metrics.api_rate_limit_remaining}\n"
            f"  CPU: {metrics.cpu_percent}%\n"
            f"  Memory: {metrics.memory_percent}%\n"
            f"  Active tasks: {metrics.active_tasks}\n"
            f"  Queued tasks: {metrics.queued_tasks}\n"
            f"  Completed/min: {metrics.completed_last_minute}\n"
        )


class SmartBatcher:
    """
    Smart batching for similar tasks

    Groups similar tasks together for batch processing
    to improve throughput and reduce overhead.
    """

    def __init__(self, max_batch_size: int = 5):
        self.max_batch_size = max_batch_size
        self.pending_batches: Dict[str, List[Dict]] = {}
        self.logger = logging.getLogger("smart-batcher")

    def get_batch_key(self, task: Dict) -> str:
        """Get batch key for task based on similarity"""
        # Group by type and similar dependencies
        task_type = task.get("type", "unknown")
        deps = frozenset(task.get("dependencies", []))
        return f"{task_type}:{hash(deps) % 1000}"

    def add_task(self, task: Dict) -> Optional[List[Dict]]:
        """
        Add task to batch

        Returns batch if it reaches max size, None otherwise
        """
        key = self.get_batch_key(task)

        if key not in self.pending_batches:
            self.pending_batches[key] = []

        self.pending_batches[key].append(task)

        # Check if batch is ready
        if len(self.pending_batches[key]) >= self.max_batch_size:
            batch = self.pending_batches[key]
            del self.pending_batches[key]
            return batch

        return None

    def flush_batch(self, key: Optional[str] = None) -> List[List[Dict]]:
        """
        Flush pending batches

        If key is None, flush all batches
        """
        if key:
            if key in self.pending_batches:
                batch = self.pending_batches[key]
                del self.pending_batches[key]
                return [batch]
            return []

        # Flush all
        batches = list(self.pending_batches.values())
        self.pending_batches.clear()
        return batches

    def get_pending_count(self) -> int:
        """Get total number of pending tasks"""
        return sum(len(batch) for batch in self.pending_batches.values())

    def should_flush(self, key: str) -> bool:
        """Check if batch should be flushed"""
        return key in self.pending_batches and len(self.pending_batches[key]) > 0


if __name__ == "__main__":
    # Test
    scaler = AutoScaler(min_concurrency=1, max_concurrency=5)

    # Simulate metrics
    class MockMetrics:
        def __init__(self):
            self.remaining = 4500
            self.cpu = 40
            self.memory = 60

    print("AutoScaler initialized")
    print(f"Current concurrency: {scaler.get_current_concurrency()}")
    print(f"Range: {scaler.min_concurrency} - {scaler.max_concurrency}")

    # Test smart batcher
    batcher = SmartBatcher(max_batch_size=3)

    tasks = [
        {"id": "T1", "type": "DB", "dependencies": []},
        {"id": "T2", "type": "DB", "dependencies": []},
        {"id": "T3", "type": "DB", "dependencies": []},
        {"id": "T4", "type": "API", "dependencies": []},
    ]

    for task in tasks:
        batch = batcher.add_task(task)
        if batch:
            print(f"\nBatch ready: {[t['id'] for t in batch]}")

    print(f"\nPending: {batcher.get_pending_count()}")
