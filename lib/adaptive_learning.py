#!/usr/bin/env python3
"""
AdaptiveLearning - Learn from execution history to improve future performance
"""

import json
import statistics
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExecutionInsight:
    """Insight from execution history"""

    pattern: str
    confidence: float
    recommendation: str
    affected_tasks: List[str]


class AdaptiveLearning:
    """
    Adaptive learning from historical execution data.

    Analyzes past executions to:
    - Identify success patterns
    - Predict failure causes
    - Optimize configurations
    - Recommend improvements
    """

    def __init__(self, data_dir: str = ".jules/learning"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.execution_history: List[Dict] = []
        self.task_patterns: Dict[str, List[Dict]] = defaultdict(list)
        self.failure_patterns: Dict[str, int] = defaultdict(int)
        self.success_patterns: Dict[str, int] = defaultdict(int)

        self._load_history()

    def _load_history(self):
        """Load execution history"""
        history_file = self.data_dir / "execution_history.jsonl"
        if history_file.exists():
            with open(history_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        self.execution_history.append(entry)

                        # Categorize
                        task_type = entry.get("task_type", "unknown")
                        self.task_patterns[task_type].append(entry)

                        if entry.get("success"):
                            self._extract_success_patterns(entry)
                        else:
                            self._extract_failure_patterns(entry)
                    except json.JSONDecodeError:
                        continue

    def _extract_success_patterns(self, entry: Dict):
        """Extract patterns from successful execution"""
        patterns = []

        # Duration patterns
        duration = entry.get("duration_seconds", 0)
        if duration < 300:
            patterns.append("fast_execution")

        # Retry patterns
        retries = entry.get("retry_count", 0)
        if retries == 0:
            patterns.append("first_try_success")

        # File patterns
        files = entry.get("files_created", [])
        if files:
            if any("test" in f.lower() for f in files):
                patterns.append("includes_tests")

        for p in patterns:
            self.success_patterns[p] += 1

    def _extract_failure_patterns(self, entry: Dict):
        """Extract patterns from failed execution"""
        patterns = []

        # Error type patterns
        error = entry.get("error", "").lower()
        if "timeout" in error:
            patterns.append("timeout_failure")
        if "rate limit" in error:
            patterns.append("rate_limit_failure")
        if "validation" in error:
            patterns.append("validation_failure")

        # Duration patterns (long running before failure)
        duration = entry.get("duration_seconds", 0)
        if duration > 600:
            patterns.append("long_running_before_failure")

        for p in patterns:
            self.failure_patterns[p] += 1

    def record_execution(self, execution: Dict):
        """Record a new execution"""
        # Add timestamp
        execution["recorded_at"] = datetime.now().isoformat()

        # Save to file
        history_file = self.data_dir / "execution_history.jsonl"
        with open(history_file, "a") as f:
            f.write(json.dumps(execution) + "\n")

        # Update in-memory data
        self.execution_history.append(execution)
        task_type = execution.get("task_type", "unknown")
        self.task_patterns[task_type].append(execution)

        if execution.get("success"):
            self._extract_success_patterns(execution)
        else:
            self._extract_failure_patterns(execution)

    def get_success_rate_by_type(self) -> Dict[str, float]:
        """Get success rate by task type"""
        rates = {}

        for task_type, executions in self.task_patterns.items():
            total = len(executions)
            successes = sum(1 for e in executions if e.get("success"))
            rates[task_type] = successes / total if total > 0 else 0.0

        return rates

    def get_average_duration_by_type(self) -> Dict[str, Dict]:
        """Get average duration statistics by task type"""
        stats = {}

        for task_type, executions in self.task_patterns.items():
            durations = [
                e.get("duration_seconds", 0)
                for e in executions
                if e.get("duration_seconds")
            ]

            if durations:
                stats[task_type] = {
                    "mean": statistics.mean(durations),
                    "median": statistics.median(durations),
                    "std_dev": statistics.stdev(durations) if len(durations) > 1 else 0,
                    "min": min(durations),
                    "max": max(durations),
                    "samples": len(durations),
                }

        return stats

    def identify_high_risk_tasks(self) -> List[Dict]:
        """Identify task types with high failure rates"""
        high_risk = []

        for task_type, rate in self.get_success_rate_by_type().items():
            if rate < 0.7:  # Less than 70% success
                executions = self.task_patterns[task_type]
                total = len(executions)

                high_risk.append(
                    {
                        "task_type": task_type,
                        "success_rate": rate,
                        "total_executions": total,
                        "failures": int(total * (1 - rate)),
                    }
                )

        # Sort by failure rate
        high_risk.sort(key=lambda x: x["success_rate"])

        return high_risk

    def recommend_optimal_concurrency(self) -> int:
        """Recommend optimal concurrency based on history"""
        # Analyze relationship between concurrency and success rate
        concurrency_success = defaultdict(lambda: {"successes": 0, "total": 0})

        for entry in self.execution_history:
            concurrency = entry.get("concurrency", 1)
            success = entry.get("success", False)

            concurrency_success[concurrency]["total"] += 1
            if success:
                concurrency_success[concurrency]["successes"] += 1

        # Find concurrency with best success rate
        best_concurrency = 1
        best_rate = 0.0

        for concurrency, data in concurrency_success.items():
            if data["total"] >= 5:  # Need sufficient samples
                rate = data["successes"] / data["total"]
                if rate > best_rate:
                    best_rate = rate
                    best_concurrency = concurrency

        return best_concurrency

    def recommend_retry_config(self) -> Dict:
        """Recommend optimal retry configuration"""
        # Analyze retry patterns
        retry_success = defaultdict(lambda: {"successes": 0, "total": 0})

        for entry in self.execution_history:
            retries = entry.get("retry_count", 0)
            success = entry.get("success", False)

            retry_success[retries]["total"] += 1
            if success:
                retry_success[retries]["successes"] += 1

        # Find optimal retry count
        optimal_retries = 2  # Default
        best_rate = 0.0

        for retries, data in retry_success.items():
            if data["total"] >= 3:
                rate = data["successes"] / data["total"]
                if rate > best_rate and retries <= 5:
                    best_rate = rate
                    optimal_retries = retries

        return {
            "max_retries": optimal_retries,
            "base_delay_seconds": 1.0,
            "max_delay_seconds": 60.0,
        }

    def generate_insights(self) -> List[ExecutionInsight]:
        """Generate actionable insights from execution history"""
        insights = []

        # Insight 1: High failure rate tasks
        high_risk = self.identify_high_risk_tasks()
        if high_risk:
            for task in high_risk[:3]:
                insights.append(
                    ExecutionInsight(
                        pattern=f"{task['task_type']} tasks have {task['success_rate']:.1%} success rate",
                        confidence=0.8,
                        recommendation=f"Consider adding more guardrails or breaking down {task['task_type']} tasks",
                        affected_tasks=[task["task_type"]],
                    )
                )

        # Insight 2: Common failure patterns
        common_failures = sorted(
            self.failure_patterns.items(), key=lambda x: x[1], reverse=True
        )[:3]

        for pattern, count in common_failures:
            insights.append(
                ExecutionInsight(
                    pattern=f"{pattern} occurred {count} times",
                    confidence=0.7,
                    recommendation=self._get_recommendation_for_pattern(pattern),
                    affected_tasks=[],
                )
            )

        # Insight 3: Success patterns
        common_success = sorted(
            self.success_patterns.items(), key=lambda x: x[1], reverse=True
        )[:3]

        for pattern, count in common_success:
            insights.append(
                ExecutionInsight(
                    pattern=f"{pattern} observed in {count} successful tasks",
                    confidence=0.6,
                    recommendation=f"Encourage {pattern} in future tasks",
                    affected_tasks=[],
                )
            )

        return insights

    def _get_recommendation_for_pattern(self, pattern: str) -> str:
        """Get recommendation for a failure pattern"""
        recommendations = {
            "timeout_failure": "Increase timeout values or add circuit breaker protection",
            "rate_limit_failure": "Implement better rate limiting and request throttling",
            "validation_failure": "Add pre-validation checks and improve test coverage",
            "long_running_before_failure": "Add intermediate checkpoints and progress monitoring",
        }
        return recommendations.get(pattern, "Review and address root cause")

    def generate_learning_report(self) -> Dict:
        """Generate comprehensive learning report"""
        total_executions = len(self.execution_history)

        if total_executions == 0:
            return {"status": "no_data"}

        successes = sum(1 for e in self.execution_history if e.get("success"))

        return {
            "total_executions": total_executions,
            "success_rate": successes / total_executions,
            "success_count": successes,
            "failure_count": total_executions - successes,
            "by_type": self.get_success_rate_by_type(),
            "duration_stats": self.get_average_duration_by_type(),
            "high_risk_tasks": self.identify_high_risk_tasks(),
            "recommended_concurrency": self.recommend_optimal_concurrency(),
            "recommended_retry_config": self.recommend_retry_config(),
            "insights": [
                {
                    "pattern": i.pattern,
                    "confidence": i.confidence,
                    "recommendation": i.recommendation,
                }
                for i in self.generate_insights()
            ],
        }

    def get_predicted_success_rate(self, task_type: str, features: Dict) -> float:
        """Predict success rate for a task based on type and features"""
        # Get base rate for type
        base_rate = self.get_success_rate_by_type().get(task_type, 0.7)

        # Adjust based on features
        adjustment = 0.0

        # Feature: has_tests
        if features.get("has_tests"):
            test_success = self._get_success_rate_for_feature("includes_tests")
            if test_success:
                adjustment += (test_success - base_rate) * 0.3

        # Feature: retry_count
        if features.get("retry_count", 0) > 0:
            adjustment -= 0.1  # Previous failures indicate risk

        # Clamp to [0, 1]
        return max(0.0, min(1.0, base_rate + adjustment))

    def _get_success_rate_for_feature(self, feature: str) -> Optional[float]:
        """Get success rate for tasks with a specific feature"""
        # Simplified - would need more sophisticated matching
        return None

    def export_training_data(self) -> List[Dict]:
        """Export data for external ML training"""
        return [
            {
                "task_type": e.get("task_type"),
                "features": {
                    "file_count": len(e.get("files_created", [])),
                    "has_tests": any(
                        "test" in f.lower() for f in e.get("files_created", [])
                    ),
                    "retry_count": e.get("retry_count", 0),
                    "duration_seconds": e.get("duration_seconds", 0),
                },
                "label": "success" if e.get("success") else "failure",
            }
            for e in self.execution_history
        ]


if __name__ == "__main__":
    # Test
    learner = AdaptiveLearning()

    # Simulate recording executions
    for i in range(10):
        learner.record_execution(
            {
                "task_type": "API",
                "success": i < 7,
                "duration_seconds": 100 + i * 10,
                "retry_count": 0 if i < 7 else 1,
                "files_created": ["controller.php", "test.php"]
                if i < 7
                else ["controller.php"],
            }
        )

    # Generate report
    report = learner.generate_learning_report()

    print("Learning Report:")
    print(f"  Total executions: {report['total_executions']}")
    print(f"  Success rate: {report['success_rate']:.1%}")
    print(f"\nBy Type:")
    for task_type, rate in report["by_type"].items():
        print(f"  {task_type}: {rate:.1%}")

    print(f"\nRecommended concurrency: {report['recommended_concurrency']}")
    print(f"Recommended retry config: {report['recommended_retry_config']}")

    print(f"\nInsights:")
    for insight in report["insights"]:
        print(f"  - {insight['pattern']} (confidence: {insight['confidence']:.1%})")
        print(f"    → {insight['recommendation']}")
