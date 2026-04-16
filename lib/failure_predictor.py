#!/usr/bin/env python3
"""
Failure Predictor - ML-based risk scoring for tasks

Analyzes historical execution data to predict task failure risk
and suggest optimizations.
"""

import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import math


@dataclass
class TaskFeatures:
    """Features extracted from task for risk prediction"""

    task_type: str
    dependency_count: int
    file_count: int
    has_tests: bool
    lines_of_code_estimate: int
    complexity_score: float
    historical_success_rate: float
    avg_duration_seconds: float
    retry_count: int


@dataclass
class RiskPrediction:
    """Risk prediction result"""

    task_id: str
    risk_score: float  # 0.0 - 1.0
    risk_level: str  # "low", "medium", "high", "critical"
    failure_probability: float
    estimated_duration_seconds: float
    recommendations: List[str]
    confidence: float


class FailurePredictor:
    """
    Predict task failure risk based on historical data and task characteristics

    Uses simple statistical models (no heavy ML dependencies):
    - Historical success rates by task type
    - Duration outliers
    - Complexity heuristics
    - Dependency depth analysis
    """

    def __init__(self, metrics_file: str = ".jules/metrics.json"):
        self.metrics_file = metrics_file
        self.historical_data: Dict[str, List[Dict]] = defaultdict(list)
        self.type_stats: Dict[str, Dict] = {}
        self._load_historical_data()

    def _load_historical_data(self):
        """Load historical task execution data"""
        try:
            audit_file = Path(".jules/audit.jsonl")
            if audit_file.exists():
                with open(audit_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get("event") in ["task_complete", "task_failed"]:
                                task_id = entry.get("task_id")
                                if task_id:
                                    self.historical_data[task_id].append(entry)
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

        # Calculate type statistics
        self._calculate_type_stats()

    def _calculate_type_stats(self):
        """Calculate statistics by task type"""
        type_data = defaultdict(lambda: {"success": 0, "failure": 0, "durations": []})

        for task_id, events in self.historical_data.items():
            for event in events:
                task_type = event.get("details", {}).get("task_type", "unknown")

                if event["event"] == "task_complete":
                    type_data[task_type]["success"] += 1
                    if "duration_seconds" in event.get("details", {}):
                        type_data[task_type]["durations"].append(
                            event["details"]["duration_seconds"]
                        )
                elif event["event"] == "task_failed":
                    type_data[task_type]["failure"] += 1

        for task_type, data in type_data.items():
            total = data["success"] + data["failure"]
            if total > 0:
                self.type_stats[task_type] = {
                    "success_rate": data["success"] / total,
                    "avg_duration": statistics.mean(data["durations"])
                    if data["durations"]
                    else 300,
                    "std_duration": statistics.stdev(data["durations"])
                    if len(data["durations"]) > 1
                    else 60,
                    "sample_size": total,
                }

    def extract_features(self, task: Dict) -> TaskFeatures:
        """Extract features from task"""
        # Task type
        task_type = task.get("type", "unknown")

        # Dependencies
        deps = task.get("dependencies", [])
        dependency_count = len(deps)

        # Files
        files = task.get("files_expected", [])
        file_count = len(files)

        # Has tests
        has_tests = any("test" in f.lower() for f in files)

        # Estimate lines of code (rough heuristic)
        lines_estimate = self._estimate_lines_of_code(files)

        # Complexity score based on various factors
        complexity = self._calculate_complexity(task, files)

        # Historical stats
        historical_success = self.type_stats.get(task_type, {}).get("success_rate", 0.8)
        avg_duration = self.type_stats.get(task_type, {}).get("avg_duration", 300)

        # Previous retries
        retry_count = task.get("retry_count", 0)

        return TaskFeatures(
            task_type=task_type,
            dependency_count=dependency_count,
            file_count=file_count,
            has_tests=has_tests,
            lines_of_code_estimate=lines_estimate,
            complexity_score=complexity,
            historical_success_rate=historical_success,
            avg_duration_seconds=avg_duration,
            retry_count=retry_count,
        )

    def _estimate_lines_of_code(self, files: List[str]) -> int:
        """Estimate lines of code based on file patterns"""
        estimates = {
            ".php": 100,
            ".py": 80,
            ".js": 60,
            ".ts": 60,
            ".java": 150,
            ".go": 80,
            ".rs": 80,
        }

        total = 0
        for f in files:
            for ext, avg_lines in estimates.items():
                if f.endswith(ext):
                    total += avg_lines
                    break
            else:
                total += 50  # Default estimate

        return total

    def _calculate_complexity(self, task: Dict, files: List[str]) -> float:
        """Calculate complexity score (0.0 - 1.0)"""
        score = 0.0

        # Base complexity by task type
        type_complexity = {
            "DB": 0.7,  # Database migrations are risky
            "API": 0.6,  # API changes affect consumers
            "UI": 0.4,  # UI changes are lower risk
            "Test": 0.3,  # Tests are low risk
            "Refactor": 0.5,
            "Config": 0.8,  # Config changes can break everything
        }
        score += type_complexity.get(task.get("type", ""), 0.5)

        # More files = more complex
        file_count = len(files)
        if file_count > 10:
            score += 0.2
        elif file_count > 5:
            score += 0.1

        # More acceptance criteria = more complex
        criteria = task.get("acceptance_criteria", [])
        if len(criteria) > 5:
            score += 0.1

        # Has dependencies
        if task.get("dependencies"):
            score += 0.1 * len(task["dependencies"])

        return min(score, 1.0)

    def predict(self, task: Dict) -> RiskPrediction:
        """Predict failure risk for a task"""
        features = self.extract_features(task)

        # Calculate base risk score
        risk_components = []

        # 1. Historical success rate (inverse)
        historical_risk = 1.0 - features.historical_success_rate
        risk_components.append(("historical", historical_risk, 0.3))

        # 2. Complexity
        complexity_risk = features.complexity_score
        risk_components.append(("complexity", complexity_risk, 0.25))

        # 3. File count (diminishing returns)
        if features.file_count > 10:
            file_risk = 0.3
        elif features.file_count > 5:
            file_risk = 0.2
        else:
            file_risk = 0.1
        risk_components.append(("file_count", file_risk, 0.15))

        # 4. Retry count (indicates previous failures)
        retry_risk = min(features.retry_count * 0.15, 0.4)
        risk_components.append(("retries", retry_risk, 0.2))

        # 5. Dependency depth
        dep_risk = min(features.dependency_count * 0.05, 0.3)
        risk_components.append(("dependencies", dep_risk, 0.1))

        # Calculate weighted average
        total_weight = sum(w for _, _, w in risk_components)
        weighted_sum = sum(r * w for _, r, w in risk_components)
        risk_score = weighted_sum / total_weight if total_weight > 0 else 0.5

        # Adjust based on sample size (lower confidence with less data)
        sample_size = self.type_stats.get(features.task_type, {}).get("sample_size", 0)
        confidence = min(sample_size / 10, 1.0)  # Max confidence after 10 samples

        # Determine risk level
        if risk_score < 0.3:
            risk_level = "low"
        elif risk_score < 0.5:
            risk_level = "medium"
        elif risk_score < 0.7:
            risk_level = "high"
        else:
            risk_level = "critical"

        # Generate recommendations
        recommendations = self._generate_recommendations(features, risk_components)

        # Estimate duration with safety margin based on risk
        base_duration = features.avg_duration_seconds
        safety_multiplier = 1.0 + (
            risk_score * 0.5
        )  # Up to 50% extra time for high risk
        estimated_duration = base_duration * safety_multiplier

        return RiskPrediction(
            task_id=task.get("id", "unknown"),
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            failure_probability=round(risk_score * 100, 1),
            estimated_duration_seconds=round(estimated_duration, 0),
            recommendations=recommendations,
            confidence=round(confidence, 2),
        )

    def _generate_recommendations(
        self, features: TaskFeatures, risk_components: List[Tuple[str, float, float]]
    ) -> List[str]:
        """Generate recommendations based on risk factors"""
        recommendations = []

        # Sort by risk contribution
        sorted_components = sorted(
            risk_components, key=lambda x: x[1] * x[2], reverse=True
        )

        for component_name, risk_value, weight in sorted_components[:3]:
            if component_name == "historical" and risk_value > 0.3:
                recommendations.append(
                    f"Task type '{features.task_type}' has low historical success rate. "
                    "Consider breaking into smaller tasks."
                )
            elif component_name == "complexity" and risk_value > 0.6:
                recommendations.append(
                    "High complexity detected. Ensure comprehensive test coverage."
                )
            elif component_name == "file_count" and risk_value > 0.2:
                recommendations.append(
                    f"Many files ({features.file_count}) being modified. "
                    "Consider splitting across multiple tasks."
                )
            elif component_name == "retries" and features.retry_count > 0:
                recommendations.append(
                    f"Task has failed {features.retry_count} times previously. "
                    "Review failure logs before retry."
                )
            elif component_name == "dependencies":
                recommendations.append(
                    f"Task depends on {features.dependency_count} other tasks. "
                    "Monitor dependency completion status closely."
                )

        # General recommendations
        if not features.has_tests:
            recommendations.append("No test files detected. Add tests to reduce risk.")

        if features.lines_of_code_estimate > 500:
            recommendations.append(
                f"Large change estimated ({features.lines_of_code_estimate} lines). "
                "Consider incremental approach."
            )

        return recommendations

    def get_batch_risk_analysis(self, tasks: List[Dict]) -> Dict:
        """Analyze risk for a batch of tasks"""
        predictions = [self.predict(task) for task in tasks]

        if not predictions:
            return {"error": "No tasks to analyze"}

        # Aggregate statistics
        risk_distribution = defaultdict(int)
        for p in predictions:
            risk_distribution[p.risk_level] += 1

        avg_risk = sum(p.risk_score for p in predictions) / len(predictions)
        high_risk_tasks = [
            p for p in predictions if p.risk_level in ["high", "critical"]
        ]

        return {
            "total_tasks": len(predictions),
            "average_risk_score": round(avg_risk, 2),
            "risk_distribution": dict(risk_distribution),
            "high_risk_count": len(high_risk_tasks),
            "high_risk_tasks": [p.task_id for p in high_risk_tasks],
            "predictions": [self._prediction_to_dict(p) for p in predictions],
        }

    def _prediction_to_dict(self, prediction: RiskPrediction) -> Dict:
        """Convert prediction to dictionary"""
        return {
            "task_id": prediction.task_id,
            "risk_score": prediction.risk_score,
            "risk_level": prediction.risk_level,
            "failure_probability": prediction.failure_probability,
            "estimated_duration_seconds": prediction.estimated_duration_seconds,
            "recommendations": prediction.recommendations,
            "confidence": prediction.confidence,
        }

    def should_add_guardrails(self, task: Dict) -> bool:
        """Determine if task needs extra guardrails"""
        prediction = self.predict(task)
        return prediction.risk_level in ["high", "critical"]

    def suggest_enhanced_prompt(
        self, task: Dict, failure_reason: Optional[str] = None
    ) -> str:
        """Suggest enhanced prompt based on predicted risks"""
        prediction = self.predict(task)

        enhancements = []

        # Add risk-based guidance
        if prediction.risk_level == "high":
            enhancements.append(
                "\n⚠️ **HIGH RISK TASK**: This task has been flagged as high risk. "
                "Please be extra careful and validate all changes thoroughly."
            )
        elif prediction.risk_level == "critical":
            enhancements.append(
                "\n🚨 **CRITICAL RISK TASK**: This is a critical-risk task. "
                "Consider manual review or breaking into smaller tasks."
            )

        # Add recommendations
        for rec in prediction.recommendations[:3]:
            enhancements.append(f"\n💡 **Recommendation**: {rec}")

        # Add failure context if available
        if failure_reason:
            enhancements.append(
                f"\n📝 **Previous Failure**: {failure_reason}\n"
                "Please address this specific issue in your implementation."
            )

        return "\n".join(enhancements)


if __name__ == "__main__":
    # Test
    predictor = FailurePredictor()

    test_task = {
        "id": "T1",
        "type": "DB",
        "title": "Add user authentication",
        "dependencies": ["T0"],
        "files_expected": [
            "database/migrations/001_add_users.php",
            "app/Models/User.php",
            "tests/Feature/UserTest.php",
        ],
        "acceptance_criteria": [
            "Users can register",
            "Users can login",
            "Passwords are hashed",
        ],
        "retry_count": 1,
    }

    prediction = predictor.predict(test_task)

    print("Risk Prediction:")
    print(f"  Task: {prediction.task_id}")
    print(f"  Risk Score: {prediction.risk_score}")
    print(f"  Risk Level: {prediction.risk_level}")
    print(f"  Failure Probability: {prediction.failure_probability}%")
    print(f"  Estimated Duration: {prediction.estimated_duration_seconds}s")
    print(f"  Confidence: {prediction.confidence}")
    print("\nRecommendations:")
    for rec in prediction.recommendations:
        print(f"  - {rec}")

    print("\n" + "=" * 60)
    print("Enhanced Prompt Suggestion:")
    print("=" * 60)
    print(predictor.suggest_enhanced_prompt(test_task, "Migration syntax error"))
