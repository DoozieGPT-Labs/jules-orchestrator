#!/usr/bin/env python3
"""
Circuit Breaker Pattern for resilient external API calls
"""

import time
import logging
from enum import Enum, auto
from typing import Callable, Optional, Any, Dict
from datetime import datetime, timedelta
from functools import wraps


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = auto()  # Normal operation
    OPEN = auto()  # Failing, reject calls
    HALF_OPEN = auto()  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern for external API resilience

    - CLOSED: Normal operation, calls pass through
    - OPEN: After threshold failures, calls fail fast
    - HALF_OPEN: After timeout, allow limited test calls
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        expected_exception: type = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self.logger = logging.getLogger(f"circuit-breaker-{name}")

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""

        if self.state == CircuitState.OPEN:
            # Check if we should try recovery
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service temporarily unavailable."
                )

        elif self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' HALF_OPEN limit reached."
                )
            self.half_open_calls += 1

        # Attempt the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery"""
        if self.last_failure_time is None:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN"""
        self.logger.info(f"Circuit '{self.name}' transitioning OPEN -> HALF_OPEN")
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.failure_count = 0
        self.success_count = 0

    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            # If enough successes in half-open, close the circuit
            if self.success_count >= self.half_open_max_calls:
                self.logger.info(
                    f"Circuit '{self.name}' transitioning HALF_OPEN -> CLOSED"
                )
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.half_open_calls = 0

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            # Failed during test, go back to open
            self.logger.warning(
                f"Circuit '{self.name}' test failed, transitioning HALF_OPEN -> OPEN"
            )
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            # Too many failures, open the circuit
            self.logger.error(
                f"Circuit '{self.name}' threshold reached ({self.failure_count}), "
                f"transitioning CLOSED -> OPEN"
            )
            self.state = CircuitState.OPEN

    def force_open(self, reason: str = "manual"):
        """Manually open the circuit"""
        self.logger.warning(f"Circuit '{self.name}' manually opened: {reason}")
        self.state = CircuitState.OPEN
        self.last_failure_time = datetime.now()

    def force_close(self, reason: str = "manual"):
        """Manually close the circuit"""
        self.logger.info(f"Circuit '{self.name}' manually closed: {reason}")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit state"""
        return {
            "name": self.name,
            "state": self.state.name,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "half_open_calls": self.half_open_calls,
            "last_failure": self.last_failure_time.isoformat()
            if self.last_failure_time
            else None,
        }


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""

    pass


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    def register(self, name: str, **kwargs) -> CircuitBreaker:
        """Register a new circuit breaker"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, **kwargs)
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._breakers.get(name)

    def get_all_states(self) -> Dict[str, Dict]:
        """Get states of all circuit breakers"""
        return {name: cb.get_state() for name, cb in self._breakers.items()}

    def reset_all(self):
        """Reset all circuit breakers to closed"""
        for cb in self._breakers.values():
            cb.force_close("bulk_reset")


# Global registry
_registry = CircuitBreakerRegistry()


def circuit_breaker(name: str, **kwargs):
    """Decorator for applying circuit breaker to functions"""
    breaker = _registry.register(name, **kwargs)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        # Attach breaker to function for monitoring
        wrapper._circuit_breaker = breaker
        return wrapper

    return decorator


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get circuit breaker by name"""
    return _registry.get(name)


def get_all_circuit_states() -> Dict[str, Dict]:
    """Get all circuit breaker states"""
    return _registry.get_all_states()


# Convenience breaker for common services
GITHUB_CIRCUIT = "github_api"
JULES_CIRCUIT = "jules_api"


def init_default_circuits():
    """Initialize default circuit breakers"""
    _registry.register(
        GITHUB_CIRCUIT,
        failure_threshold=5,
        recovery_timeout=60,
        half_open_max_calls=3,
        expected_exception=Exception,
    )


if __name__ == "__main__":
    # Test circuit breaker
    init_default_circuits()

    breaker = get_circuit_breaker(GITHUB_CIRCUIT)

    # Simulate failures
    for i in range(7):
        try:
            breaker.call(lambda: (_ for _ in ()).throw(Exception("API Error")))
        except CircuitBreakerOpen:
            print(f"Call {i + 1}: Circuit breaker OPEN")
        except Exception:
            print(f"Call {i + 1}: Normal failure")

    print(f"\nCircuit state: {breaker.get_state()}")
