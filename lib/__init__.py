"""
Jules Orchestrator Library

Background agent for async AI software factory with Google Jules.
"""

from .background_agent import JulesBackgroundAgent
from .dependency_resolver import create_execution_plan, DependencyResolver
from .resume_logic import resume_orchestration
from .skill_detector import SkillDetector, detect_and_inject_skills
from .pr_quality_gate import PRQualityGate
from .diff_intelligence import DiffIntelligence
from .replay_engine import ReplayEngine
from .memory_manager import MemoryManager, AuditLog
from .process_manager import ProcessManager, HealthChecker
from .github_utils import GitHubClient, GitHubAPIError
from .plan_validator import PlanValidator, validate_plan_file
from .state_machine import StateMachine, StateRecovery, InvalidStateTransition
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    circuit_breaker,
    get_circuit_breaker,
    get_all_circuit_states,
    GITHUB_CIRCUIT,
    JULES_CIRCUIT,
)
from .retry_manager import with_retry, github_api_retry
from .reconciliation import ReconciliationEngine, OrphanedResource
from .health_dashboard import (
    HealthDashboard,
    HealthCheckResult,
    SystemMetrics,
    generate_health_check_endpoint,
)
from .metrics import (
    MetricsCollector,
    MetricCounter,
    MetricGauge,
    MetricHistogram,
    get_metrics,
    record_metric,
    timed_metric,
)
from .failure_predictor import (
    FailurePredictor,
    TaskFeatures,
    RiskPrediction,
)
from .auto_scaler import (
    AutoScaler,
    SmartBatcher,
    ScalingMetrics,
    ScalingDecision,
)
from .cache_manager import (
    CacheManager,
    CacheEntry,
    create_github_cache,
    create_validation_cache,
    create_pr_info_cache,
)
from .failure_predictor import (
    FailurePredictor,
    TaskFeatures,
    RiskPrediction,
)
from .auto_scaler import (
    AutoScaler,
    SmartBatcher,
    ScalingMetrics,
    ScalingDecision,
)
from .performance_monitor import (
    PerformanceMonitor,
    PerformanceSnapshot,
    Bottleneck,
    BottleneckAlertManager,
)
from .self_healing import (
    SelfHealingEngine,
    HealingAction,
    HealingActionType,
    FailurePattern,
    FailurePatternLibrary,
    should_heal_task,
)
from .dependency_optimizer import (
    DependencyOptimizer,
    DependencyAnalysis,
)
from .context_injector import (
    ContextInjector,
    TaskContext,
)
from .adaptive_learning import (
    AdaptiveLearning,
    ExecutionInsight,
)

__version__ = "4.0.0"

__all__ = [
    "JulesBackgroundAgent",
    "create_execution_plan",
    "DependencyResolver",
    "resume_orchestration",
    "SkillDetector",
    "detect_and_inject_skills",
    "PRQualityGate",
    "DiffIntelligence",
    "ReplayEngine",
    "MemoryManager",
    "AuditLog",
    "ProcessManager",
    "HealthChecker",
    "GitHubClient",
    "GitHubAPIError",
    "PlanValidator",
    "validate_plan_file",
    "StateMachine",
    "StateRecovery",
    "InvalidStateTransition",
    # Phase 2 Additions
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitBreakerRegistry",
    "circuit_breaker",
    "get_circuit_breaker",
    "get_all_circuit_states",
    "GITHUB_CIRCUIT",
    "JULES_CIRCUIT",
    "RetryManager",
    "RetryConfig",
    "with_retry",
    "github_api_retry",
    "jules_api_retry",
    "memory_io_retry",
    "ReconciliationEngine",
    "OrphanedResource",
]
