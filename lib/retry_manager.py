#!/usr/bin/env python3
"""
Retry Manager - Exponential backoff with jitter for resilient retries
"""

import time
import random
import logging
from typing import Callable, Optional, Dict, Any, Type
from functools import wraps
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_max: float = 0.5
    retryable_exceptions: tuple = (Exception,)
    on_retry: Optional[Callable] = None
    on_success: Optional[Callable] = None
    on_failure: Optional[Callable] = None


class RetryManager:
    """
    Retry manager with exponential backoff and jitter

    Implements the "Full Jitter" algorithm from AWS Architecture Blog:
    sleep = random(0, min(base * 2^attempt, max))
    """

    def __init__(self, config: Optional[RetryConfig] = None, name: str = "default"):
        self.config = config or RetryConfig()
        self.name = name
        self.logger = logging.getLogger(f"retry-manager-{name}")
        self._stats = {
            "total_calls": 0,
            "success_first_try": 0,
            "success_after_retry": 0,
            "failures": 0,
        }

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and jitter

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Calculate exponential delay
        delay = self.config.base_delay * (self.config.exponential_base**attempt)

        # Cap at max delay
        delay = min(delay, self.config.max_delay)

        # Add jitter to prevent thundering herd
        if self.config.jitter:
            jitter_amount = delay * random.uniform(0, self.config.jitter_max)
            delay = (
                delay
                - jitter_amount
                + (delay * random.uniform(0, self.config.jitter_max))
            )

        return delay

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        context = {
            "attempt": 0,
            "start_time": datetime.now(),
            "delays": [],
        }

        for attempt in range(self.config.max_retries + 1):
            context["attempt"] = attempt

            try:
                self._stats["total_calls"] += 1
                result = func(*args, **kwargs)

                if attempt == 0:
                    self._stats["success_first_try"] += 1
                else:
                    self._stats["success_after_retry"] += 1

                if self.config.on_success:
                    self.config.on_success(context, result)

                self.logger.info(
                    f"Function succeeded on attempt {attempt + 1} "
                    f"(after {self._get_elapsed(context)}s)"
                )

                return result

            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt < self.config.max_retries:
                    delay = self.calculate_delay(attempt)
                    context["delays"].append(delay)

                    self.logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    if self.config.on_retry:
                        self.config.on_retry(context, e)

                    time.sleep(delay)
                else:
                    self._stats["failures"] += 1
                    self.logger.error(
                        f"All {self.config.max_retries + 1} attempts failed. "
                        f"Total time: {self._get_elapsed(context)}s"
                    )

                    if self.config.on_failure:
                        self.config.on_failure(context, e)

                    raise last_exception

        # Should never reach here
        raise last_exception

    def _get_elapsed(self, context: Dict) -> float:
        """Get elapsed time since start"""
        return (datetime.now() - context["start_time"]).total_seconds()

    def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics"""
        total = self._stats["total_calls"]
        if total == 0:
            return {**self._stats, "success_rate": 0.0, "retry_rate": 0.0}

        return {
            **self._stats,
            "success_rate": (
                self._stats["success_first_try"] + self._stats["success_after_retry"]
            )
            / total,
            "first_try_rate": self._stats["success_first_try"] / total,
            "retry_rate": self._stats["success_after_retry"] / total,
            "failure_rate": self._stats["failures"] / total,
        }

    def reset_stats(self):
        """Reset statistics"""
        self._stats = {
            "total_calls": 0,
            "success_first_try": 0,
            "success_after_retry": 0,
            "failures": 0,
        }


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
    name: str = "default",
):
    """Decorator for adding retry logic to functions"""
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
    )
    manager = RetryManager(config, name)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return manager.execute(func, *args, **kwargs)

        wrapper._retry_manager = manager
        return wrapper

    return decorator


# Pre-configured retry strategies


def github_api_retry():
    """Retry config for GitHub API calls"""
    return with_retry(
        max_retries=5,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        retryable_exceptions=(Exception,),
        name="github_api",
    )


def jules_api_retry():
    """Retry config for Jules API calls"""
    return with_retry(
        max_retries=3,
        base_delay=5.0,
        max_delay=300.0,  # 5 minutes max
        exponential_base=2.0,
        jitter=True,
        retryable_exceptions=(Exception,),
        name="jules_api",
    )


def memory_io_retry():
    """Retry config for file/memory operations"""
    return with_retry(
        max_retries=3,
        base_delay=0.5,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=False,  # No jitter for local operations
        retryable_exceptions=(IOError, OSError),
        name="memory_io",
    )


if __name__ == "__main__":
    # Test retry manager
    config = RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0, jitter=True)

    manager = RetryManager(config, "test")

    attempt_count = 0

    def flaky_function():
        attempt_count = [0]
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ValueError(f"Simulated failure #{attempt_count}")
        return "Success!"

    try:
        result = manager.execute(flaky_function)
        print(f"Result: {result}")
        print(f"Stats: {manager.get_stats()}")
    except Exception as e:
        print(f"Failed: {e}")

    # Test delays
    print("\nDelay calculations:")
    for i in range(5):
        delay = manager.calculate_delay(i)
        print(f"  Attempt {i + 1}: {delay:.2f}s")
