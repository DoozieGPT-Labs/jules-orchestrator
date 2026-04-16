#!/usr/bin/env python3
"""
Metrics Collector - Collect and expose metrics for Phase 2 features
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import threading


@dataclass
class MetricValue:
    """Single metric value with timestamp"""

    value: float
    timestamp: str
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricCounter:
    """Counter metric that only increases"""

    name: str
    description: str
    value: float = 0.0
    values: List[MetricValue] = field(default_factory=list)

    def increment(self, amount: float = 1.0, labels: Optional[Dict] = None):
        """Increment counter"""
        self.value += amount
        self.values.append(
            MetricValue(
                value=self.value,
                timestamp=datetime.now().isoformat(),
                labels=labels or {},
            )
        )

    def get(self) -> float:
        """Get current value"""
        return self.value


@dataclass
class MetricGauge:
    """Gauge metric that can go up or down"""

    name: str
    description: str
    value: float = 0.0
    values: List[MetricValue] = field(default_factory=list)

    def set(self, value: float, labels: Optional[Dict] = None):
        """Set gauge value"""
        self.value = value
        self.values.append(
            MetricValue(
                value=value, timestamp=datetime.now().isoformat(), labels=labels or {}
            )
        )

    def increment(self, amount: float = 1.0, labels: Optional[Dict] = None):
        """Increment gauge"""
        self.set(self.value + amount, labels)

    def decrement(self, amount: float = 1.0, labels: Optional[Dict] = None):
        """Decrement gauge"""
        self.set(self.value - amount, labels)

    def get(self) -> float:
        """Get current value"""
        return self.value


@dataclass
class MetricHistogram:
    """Histogram metric for tracking distributions"""

    name: str
    description: str
    buckets: List[float] = field(
        default_factory=lambda: [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    )
    values: List[MetricValue] = field(default_factory=list)
    sum_value: float = 0.0
    count: int = 0

    def observe(self, value: float, labels: Optional[Dict] = None):
        """Observe a value"""
        self.values.append(
            MetricValue(
                value=value, timestamp=datetime.now().isoformat(), labels=labels or {}
            )
        )
        self.sum_value += value
        self.count += 1

    def get_bucket_counts(self) -> Dict[float, int]:
        """Get count of values in each bucket"""
        counts = {b: 0 for b in self.buckets}
        counts["+Inf"] = 0

        for v in self.values:
            placed = False
            for bucket in sorted(self.buckets):
                if v.value <= bucket:
                    counts[bucket] += 1
                    placed = True
                    break
            if not placed:
                counts["+Inf"] += 1

        return counts


class MetricsCollector:
    """
    Central metrics collector for Jules Orchestrator

    Tracks:
    - Circuit breaker events
    - Retry attempts and successes
    - Reconciliation runs
    - State transitions
    - Task execution times
    - API call latencies
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.metrics_file = Path(".jules/metrics.json")
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Counters
        self.counters: Dict[str, MetricCounter] = {}
        self.gauges: Dict[str, MetricGauge] = {}
        self.histograms: Dict[str, MetricHistogram] = {}

        # Initialize Phase 2 metrics
        self._init_phase2_metrics()

    def _init_phase2_metrics(self):
        """Initialize metrics for Phase 2 features"""
        # Circuit breaker metrics
        self.counters["circuit_breaker_opens"] = MetricCounter(
            "circuit_breaker_opens", "Number of times circuit breaker opened"
        )
        self.counters["circuit_breaker_closes"] = MetricCounter(
            "circuit_breaker_closes", "Number of times circuit breaker closed"
        )
        self.counters["circuit_breaker_failures"] = MetricCounter(
            "circuit_breaker_failures", "Number of calls that failed with circuit open"
        )

        # Retry metrics
        self.counters["retry_attempts"] = MetricCounter(
            "retry_attempts", "Total number of retry attempts"
        )
        self.counters["retry_successes"] = MetricCounter(
            "retry_successes", "Number of successful retries"
        )
        self.counters["retry_failures"] = MetricCounter(
            "retry_failures", "Number of failed retries (exhausted)"
        )
        self.histograms["retry_duration_seconds"] = MetricHistogram(
            "retry_duration_seconds",
            "Time spent in retry attempts",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )

        # Reconciliation metrics
        self.counters["reconciliation_runs"] = MetricCounter(
            "reconciliation_runs", "Number of reconciliation runs"
        )
        self.counters["orphaned_resources_found"] = MetricCounter(
            "orphaned_resources_found", "Number of orphaned resources detected"
        )
        self.counters["orphaned_resources_fixed"] = MetricCounter(
            "orphaned_resources_fixed", "Number of orphaned resources auto-fixed"
        )
        self.gauges["orphaned_resources_pending"] = MetricGauge(
            "orphaned_resources_pending",
            "Number of orphaned resources awaiting manual fix",
        )

        # State transition metrics
        self.counters["state_transitions_total"] = MetricCounter(
            "state_transitions_total", "Total number of state transitions"
        )
        self.counters["state_transition_failures"] = MetricCounter(
            "state_transition_failures", "Number of invalid state transitions attempted"
        )
        self.histograms["state_transition_latency_seconds"] = MetricHistogram(
            "state_transition_latency_seconds",
            "Time spent in state transitions",
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0],
        )

        # Task execution metrics
        self.counters["tasks_created"] = MetricCounter(
            "tasks_created", "Number of tasks created"
        )
        self.counters["tasks_completed"] = MetricCounter(
            "tasks_completed", "Number of tasks completed"
        )
        self.counters["tasks_failed"] = MetricCounter(
            "tasks_failed", "Number of tasks failed"
        )
        self.counters["tasks_blocked"] = MetricCounter(
            "tasks_blocked", "Number of tasks blocked"
        )
        self.gauges["tasks_in_progress"] = MetricGauge(
            "tasks_in_progress", "Number of tasks currently in progress"
        )
        self.histograms["task_execution_duration_seconds"] = MetricHistogram(
            "task_execution_duration_seconds",
            "Time to complete a task",
            buckets=[60, 300, 600, 1800, 3600, 7200],
        )

        # API call metrics
        self.counters["api_calls_total"] = MetricCounter(
            "api_calls_total", "Total number of API calls"
        )
        self.counters["api_call_errors"] = MetricCounter(
            "api_call_errors", "Number of API call errors"
        )
        self.histograms["api_call_latency_seconds"] = MetricHistogram(
            "api_call_latency_seconds",
            "API call latency",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )

    def counter(self, name: str) -> MetricCounter:
        """Get or create counter"""
        if name not in self.counters:
            self.counters[name] = MetricCounter(name, f"Counter: {name}")
        return self.counters[name]

    def gauge(self, name: str) -> MetricGauge:
        """Get or create gauge"""
        if name not in self.gauges:
            self.gauges[name] = MetricGauge(name, f"Gauge: {name}")
        return self.gauges[name]

    def histogram(self, name: str) -> MetricHistogram:
        """Get or create histogram"""
        if name not in self.histograms:
            self.histograms[name] = MetricHistogram(name, f"Histogram: {name}")
        return self.histograms[name]

    def record_circuit_event(self, event_type: str, circuit_name: str):
        """Record circuit breaker event"""
        if event_type == "open":
            self.counters["circuit_breaker_opens"].increment(
                labels={"circuit": circuit_name}
            )
        elif event_type == "close":
            self.counters["circuit_breaker_closes"].increment(
                labels={"circuit": circuit_name}
            )
        elif event_type == "failure":
            self.counters["circuit_breaker_failures"].increment(
                labels={"circuit": circuit_name}
            )

    def record_retry(self, success: bool, duration_seconds: float, service: str = ""):
        """Record retry attempt"""
        labels = {"service": service} if service else {}

        self.counters["retry_attempts"].increment(labels=labels)
        self.histograms["retry_duration_seconds"].observe(duration_seconds, labels)

        if success:
            self.counters["retry_successes"].increment(labels=labels)
        else:
            self.counters["retry_failures"].increment(labels=labels)

    def record_reconciliation(self, orphaned_found: int, orphaned_fixed: int):
        """Record reconciliation run"""
        self.counters["reconciliation_runs"].increment()

        if orphaned_found > 0:
            self.counters["orphaned_resources_found"].increment(amount=orphaned_found)
        if orphaned_fixed > 0:
            self.counters["orphaned_resources_fixed"].increment(amount=orphaned_fixed)

        pending = orphaned_found - orphaned_fixed
        self.gauges["orphaned_resources_pending"].set(pending)

    def record_state_transition(
        self,
        from_state: str,
        to_state: str,
        duration_seconds: float,
        success: bool = True,
    ):
        """Record state transition"""
        labels = {"from": from_state, "to": to_state}

        self.counters["state_transitions_total"].increment(labels=labels)
        self.histograms["state_transition_latency_seconds"].observe(
            duration_seconds, labels
        )

        if not success:
            self.counters["state_transition_failures"].increment(labels=labels)

    def record_task_event(
        self, event_type: str, task_id: str, duration_seconds: Optional[float] = None
    ):
        """Record task event"""
        labels = {"task_id": task_id}

        if event_type == "created":
            self.counters["tasks_created"].increment(labels=labels)
            self.gauges["tasks_in_progress"].increment()
        elif event_type == "completed":
            self.counters["tasks_completed"].increment(labels=labels)
            self.gauges["tasks_in_progress"].decrement()
            if duration_seconds:
                self.histograms["task_execution_duration_seconds"].observe(
                    duration_seconds, labels
                )
        elif event_type == "failed":
            self.counters["tasks_failed"].increment(labels=labels)
            self.gauges["tasks_in_progress"].decrement()
        elif event_type == "blocked":
            self.counters["tasks_blocked"].increment(labels=labels)
            self.gauges["tasks_in_progress"].decrement()

    def record_api_call(
        self, endpoint: str, duration_seconds: float, success: bool = True
    ):
        """Record API call"""
        labels = {"endpoint": endpoint}

        self.counters["api_calls_total"].increment(labels=labels)
        self.histograms["api_call_latency_seconds"].observe(duration_seconds, labels)

        if not success:
            self.counters["api_call_errors"].increment(labels=labels)

    def get_all_metrics(self) -> Dict:
        """Get all metrics as dictionary"""
        return {
            "timestamp": datetime.now().isoformat(),
            "counters": {
                name: {"value": c.get(), "description": c.description}
                for name, c in self.counters.items()
            },
            "gauges": {
                name: {"value": g.get(), "description": g.description}
                for name, g in self.gauges.items()
            },
            "histograms": {
                name: {
                    "count": h.count,
                    "sum": h.sum_value,
                    "buckets": h.get_bucket_counts(),
                    "description": h.description,
                }
                for name, h in self.histograms.items()
            },
        }

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus exposition format"""
        lines = []

        # Counters
        for name, counter in self.counters.items():
            lines.append(f"# HELP {name} {counter.description}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {counter.get()}")

        # Gauges
        for name, gauge in self.gauges.items():
            lines.append(f"# HELP {name} {gauge.description}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {gauge.get()}")

        # Histograms
        for name, hist in self.histograms.items():
            lines.append(f"# HELP {name} {hist.description}")
            lines.append(f"# TYPE {name} histogram")

            buckets = hist.get_bucket_counts()
            for bucket, count in buckets.items():
                bucket_label = f'le="{bucket}"' if bucket != "+Inf" else 'le="+Inf"'
                lines.append(f"{name}_bucket{{{bucket_label}}} {count}")

            lines.append(f"{name}_sum {hist.sum_value}")
            lines.append(f"{name}_count {hist.count}")

        return "\n".join(lines)

    def save(self):
        """Save metrics to file"""
        try:
            with open(self.metrics_file, "w") as f:
                json.dump(self.get_all_metrics(), f, indent=2)
        except Exception:
            pass

    def load(self) -> Optional[Dict]:
        """Load metrics from file"""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def reset(self):
        """Reset all metrics (use with caution)"""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self._init_phase2_metrics()


# Global instance
_metrics = None


def get_metrics() -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def record_metric(
    name: str, value: float, metric_type: str = "gauge", labels: Optional[Dict] = None
):
    """Convenience function to record a metric"""
    metrics = get_metrics()

    if metric_type == "counter":
        metrics.counter(name).increment(value, labels)
    elif metric_type == "gauge":
        metrics.gauge(name).set(value, labels)
    elif metric_type == "histogram":
        metrics.histogram(name).observe(value, labels)


def timed_metric(metric_name: str, metric_type: str = "histogram"):
    """Decorator to time function execution"""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start

            metrics = get_metrics()
            if metric_type == "histogram":
                metrics.histogram(f"{metric_name}_duration_seconds").observe(duration)
            elif metric_type == "gauge":
                metrics.gauge(metric_name).set(duration)

            return result

        return wrapper

    return decorator


if __name__ == "__main__":
    # Test
    metrics = get_metrics()

    # Simulate some activity
    metrics.record_circuit_event("open", "github_api")
    metrics.record_circuit_event("close", "github_api")

    metrics.record_retry(True, 2.5, "github_api")
    metrics.record_retry(False, 10.0, "github_api")

    metrics.record_reconciliation(5, 3)

    metrics.record_state_transition("pending", "issue_created", 0.1)

    metrics.record_task_event("created", "T1")
    metrics.record_task_event("completed", "T1", 300.0)

    metrics.record_api_call("/repos/{owner}/{repo}/issues", 0.5, True)

    # Export
    print("=" * 60)
    print("METRICS (JSON)")
    print("=" * 60)
    print(json.dumps(metrics.get_all_metrics(), indent=2))

    print("\n" + "=" * 60)
    print("METRICS (Prometheus)")
    print("=" * 60)
    print(metrics.export_prometheus_format())
