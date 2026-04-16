#!/usr/bin/env python3
"""
Performance Monitor - Real-time performance tracking and bottleneck detection
"""

import time
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
import threading
import logging


@dataclass
class PerformanceSnapshot:
    """Performance snapshot at a point in time"""

    timestamp: str
    cpu_percent: float
    memory_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_sent_mb: float
    network_io_recv_mb: float
    active_threads: int
    open_files: int


@dataclass
class Bottleneck:
    """Detected bottleneck"""

    type: str  # "cpu", "memory", "io", "api_rate", "task_queue"
    severity: str  # "low", "medium", "high", "critical"
    metric: str
    current_value: float
    threshold: float
    description: str
    recommendations: List[str]


class PerformanceMonitor:
    """
    Real-time performance monitoring and bottleneck detection

    Monitors:
    - System resources (CPU, memory, I/O)
    - Task execution times
    - API response times
    - Queue depths
    - Throughput rates
    """

    def __init__(self, history_minutes: int = 60):
        self.history_minutes = history_minutes
        self.logger = logging.getLogger("performance-monitor")

        # Historical data
        self.snapshots: deque = deque(
            maxlen=history_minutes * 2
        )  # 2 samples per minute
        self.task_times: Dict[str, List[float]] = defaultdict(list)
        self.api_times: Dict[str, List[float]] = defaultdict(list)

        # Current metrics
        self.current_metrics: Dict[str, Any] = {}
        self._lock = threading.RLock()

        # Thresholds
        self.thresholds = {
            "cpu_high": 80.0,
            "cpu_critical": 95.0,
            "memory_high": 85.0,
            "memory_critical": 95.0,
            "api_latency_high": 5000.0,  # 5 seconds
            "api_latency_critical": 10000.0,  # 10 seconds
            "task_duration_high": 600.0,  # 10 minutes
            "task_duration_critical": 1800.0,  # 30 minutes
            "queue_depth_high": 10,
            "queue_depth_critical": 20,
        }

    def capture_snapshot(self) -> Optional[PerformanceSnapshot]:
        """Capture current performance snapshot"""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_io_counters()
            net = psutil.net_io_counters()

            snapshot = PerformanceSnapshot(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu,
                memory_mb=memory.used / 1024 / 1024,
                disk_io_read_mb=disk.read_bytes / 1024 / 1024 if disk else 0,
                disk_io_write_mb=disk.write_bytes / 1024 / 1024 if disk else 0,
                network_io_sent_mb=net.bytes_sent / 1024 / 1024 if net else 0,
                network_io_recv_mb=net.bytes_recv / 1024 / 1024 if net else 0,
                active_threads=threading.active_count(),
                open_files=len(psutil.Process().open_files())
                if hasattr(psutil.Process(), "open_files")
                else 0,
            )

            with self._lock:
                self.snapshots.append(snapshot)

            return snapshot

        except ImportError:
            self.logger.debug("psutil not available for performance monitoring")
            return None
        except Exception as e:
            self.logger.error(f"Failed to capture snapshot: {e}")
            return None

    def record_task_duration(self, task_type: str, duration_seconds: float):
        """Record task execution duration"""
        with self._lock:
            self.task_times[task_type].append(duration_seconds)
            # Keep last 100 samples
            if len(self.task_times[task_type]) > 100:
                self.task_times[task_type] = self.task_times[task_type][-100:]

    def record_api_latency(self, endpoint: str, latency_ms: float):
        """Record API call latency"""
        with self._lock:
            self.api_times[endpoint].append(latency_ms)
            # Keep last 50 samples
            if len(self.api_times[endpoint]) > 50:
                self.api_times[endpoint] = self.api_times[endpoint][-50:]

    def detect_bottlenecks(self) -> List[Bottleneck]:
        """Detect performance bottlenecks"""
        bottlenecks = []

        # Get current snapshot
        snapshot = self.capture_snapshot()
        if not snapshot:
            return bottlenecks

        # Check CPU
        if snapshot.cpu_percent > self.thresholds["cpu_critical"]:
            bottlenecks.append(
                Bottleneck(
                    type="cpu",
                    severity="critical",
                    metric="cpu_percent",
                    current_value=snapshot.cpu_percent,
                    threshold=self.thresholds["cpu_critical"],
                    description=f"CPU usage critical: {snapshot.cpu_percent:.1f}%",
                    recommendations=[
                        "Reduce concurrent task execution",
                        "Investigate high CPU processes",
                        "Consider upgrading compute resources",
                    ],
                )
            )
        elif snapshot.cpu_percent > self.thresholds["cpu_high"]:
            bottlenecks.append(
                Bottleneck(
                    type="cpu",
                    severity="high",
                    metric="cpu_percent",
                    current_value=snapshot.cpu_percent,
                    threshold=self.thresholds["cpu_high"],
                    description=f"CPU usage high: {snapshot.cpu_percent:.1f}%",
                    recommendations=[
                        "Monitor for sustained high usage",
                        "Consider reducing parallel execution",
                    ],
                )
            )

        # Check memory
        try:
            import psutil

            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            if memory_percent > self.thresholds["memory_critical"]:
                bottlenecks.append(
                    Bottleneck(
                        type="memory",
                        severity="critical",
                        metric="memory_percent",
                        current_value=memory_percent,
                        threshold=self.thresholds["memory_critical"],
                        description=f"Memory usage critical: {memory_percent:.1f}%",
                        recommendations=[
                            "Restart agent to free memory",
                            "Check for memory leaks",
                            "Increase system memory",
                        ],
                    )
                )
            elif memory_percent > self.thresholds["memory_high"]:
                bottlenecks.append(
                    Bottleneck(
                        type="memory",
                        severity="high",
                        metric="memory_percent",
                        current_value=memory_percent,
                        threshold=self.thresholds["memory_high"],
                        description=f"Memory usage high: {memory_percent:.1f}%",
                        recommendations=[
                            "Monitor memory trends",
                            "Reduce cache sizes",
                        ],
                    )
                )
        except ImportError:
            pass

        # Check task durations
        for task_type, times in self.task_times.items():
            if len(times) >= 5:
                avg_duration = statistics.mean(times[-5:])
                if avg_duration > self.thresholds["task_duration_critical"]:
                    bottlenecks.append(
                        Bottleneck(
                            type="task_execution",
                            severity="critical",
                            metric=f"{task_type}_avg_duration",
                            current_value=avg_duration,
                            threshold=self.thresholds["task_duration_critical"],
                            description=f"{task_type} tasks taking {avg_duration:.0f}s on average",
                            recommendations=[
                                "Check for external service degradation",
                                "Review task complexity",
                                "Consider task splitting",
                            ],
                        )
                    )
                elif avg_duration > self.thresholds["task_duration_high"]:
                    bottlenecks.append(
                        Bottleneck(
                            type="task_execution",
                            severity="high",
                            metric=f"{task_type}_avg_duration",
                            current_value=avg_duration,
                            threshold=self.thresholds["task_duration_high"],
                            description=f"{task_type} tasks taking {avg_duration:.0f}s on average",
                            recommendations=[
                                "Monitor task execution times",
                                "Review for inefficiencies",
                            ],
                        )
                    )

        # Check API latencies
        for endpoint, times in self.api_times.items():
            if len(times) >= 5:
                avg_latency = statistics.mean(times[-5:])
                if avg_latency > self.thresholds["api_latency_critical"]:
                    bottlenecks.append(
                        Bottleneck(
                            type="api",
                            severity="critical",
                            metric=f"{endpoint}_avg_latency",
                            current_value=avg_latency,
                            threshold=self.thresholds["api_latency_critical"],
                            description=f"{endpoint} API calls taking {avg_latency:.0f}ms on average",
                            recommendations=[
                                "Check external service status",
                                "Consider circuit breaker",
                                "Review API rate limits",
                            ],
                        )
                    )
                elif avg_latency > self.thresholds["api_latency_high"]:
                    bottlenecks.append(
                        Bottleneck(
                            type="api",
                            severity="high",
                            metric=f"{endpoint}_avg_latency",
                            current_value=avg_latency,
                            threshold=self.thresholds["api_latency_high"],
                            description=f"{endpoint} API calls taking {avg_latency:.0f}ms on average",
                            recommendations=[
                                "Monitor API performance",
                                "Check for rate limiting",
                            ],
                        )
                    )

        return bottlenecks

    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "current": {},
            "trends": {},
            "bottlenecks": [],
        }

        # Current snapshot
        snapshot = self.capture_snapshot()
        if snapshot:
            report["current"] = {
                "cpu_percent": snapshot.cpu_percent,
                "memory_mb": round(snapshot.memory_mb, 2),
                "active_threads": snapshot.active_threads,
            }

        # Calculate trends
        with self._lock:
            if len(self.snapshots) >= 2:
                cpu_values = [s.cpu_percent for s in self.snapshots]
                report["trends"] = {
                    "cpu_avg": statistics.mean(cpu_values),
                    "cpu_max": max(cpu_values),
                    "cpu_min": min(cpu_values),
                }

        # Detect bottlenecks
        report["bottlenecks"] = [
            {
                "type": b.type,
                "severity": b.severity,
                "description": b.description,
                "recommendations": b.recommendations,
            }
            for b in self.detect_bottlenecks()
        ]

        return report

    def get_task_performance_summary(self) -> Dict:
        """Get task performance summary"""
        summary = {}

        with self._lock:
            for task_type, times in self.task_times.items():
                if times:
                    summary[task_type] = {
                        "count": len(times),
                        "avg_duration": statistics.mean(times),
                        "min_duration": min(times),
                        "max_duration": max(times),
                    }
                    if len(times) > 1:
                        summary[task_type]["std_dev"] = statistics.stdev(times)

        return summary

    def is_system_healthy(self) -> Tuple[bool, List[Bottleneck]]:
        """Check if system is healthy"""
        bottlenecks = self.detect_bottlenecks()

        # System is healthy if no critical or high severity bottlenecks
        critical_bottlenecks = [
            b for b in bottlenecks if b.severity in ["critical", "high"]
        ]

        return len(critical_bottlenecks) == 0, critical_bottlenecks


class BottleneckAlertManager:
    """
    Manages bottleneck alerts and notifications

    Prevents alert fatigue by:
    - Debouncing repeated alerts
    - Grouping similar alerts
    - Providing alert history
    """

    def __init__(self, alert_cooldown_seconds: int = 300):
        self.cooldown = alert_cooldown_seconds
        self.last_alerts: Dict[str, datetime] = {}
        self.alert_history: deque = deque(maxlen=100)
        self.logger = logging.getLogger("bottleneck-alerts")

    def should_alert(self, bottleneck: Bottleneck) -> bool:
        """Check if we should send alert for bottleneck"""
        key = f"{bottleneck.type}:{bottleneck.metric}"
        now = datetime.now()

        # Always alert for critical
        if bottleneck.severity == "critical":
            return True

        # Check cooldown
        if key in self.last_alerts:
            time_since = (now - self.last_alerts[key]).total_seconds()
            if time_since < self.cooldown:
                return False

        return True

    def record_alert(self, bottleneck: Bottleneck):
        """Record that alert was sent"""
        key = f"{bottleneck.type}:{bottleneck.metric}"
        self.last_alerts[key] = datetime.now()

        self.alert_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": bottleneck.type,
                "severity": bottleneck.severity,
                "description": bottleneck.description,
            }
        )

        self.logger.warning(f"Bottleneck alert: {bottleneck.description}")

    def get_alert_summary(self) -> Dict:
        """Get summary of recent alerts"""
        return {
            "total_alerts": len(self.alert_history),
            "by_severity": defaultdict(int),
            "by_type": defaultdict(int),
            "recent": list(self.alert_history)[-10:],
        }


if __name__ == "__main__":
    # Test
    monitor = PerformanceMonitor(history_minutes=10)

    # Simulate some data
    for i in range(10):
        monitor.record_task_duration("API", 45.0 + i * 5)
        monitor.record_api_latency("/repos/{owner}/{repo}/issues", 500.0 + i * 50)

    # Get report
    report = monitor.get_performance_report()
    print("Performance Report:")
    print(json.dumps(report, indent=2))

    # Check health
    healthy, bottlenecks = monitor.is_system_healthy()
    print(f"\nSystem Healthy: {healthy}")
    if bottlenecks:
        print(f"Bottlenecks detected: {len(bottlenecks)}")
