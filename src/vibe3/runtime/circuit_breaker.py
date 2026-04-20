"""Circuit breaker for dispatch-level failure protection.

Protects the system from cascading failures when codeagent-wrapper
encounters repeated API/token errors. Business errors (merge conflicts,
test failures) do NOT trigger the breaker.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Literal

from loguru import logger


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if recovered


# Error categories for circuit breaker decision
ErrorCategory = Literal["api_error", "business_error", "timeout", "unknown"]


def classify_failure(
    returncode: int,
    stderr: str,
    timed_out: bool = False,
) -> ErrorCategory:
    """Classify dispatch failure for circuit breaker decision.

    Args:
        returncode: Process exit code
        stderr: Standard error output
        timed_out: Whether the subprocess timed out

    Returns:
        "api_error": API/token/rate limit failure -> counts toward breaker
        "business_error": normal business failure -> does not count
        "timeout": process timeout -> counts toward breaker
        "unknown": unclassified -> counts toward breaker (conservative)
    """
    if timed_out:
        return "timeout"

    if returncode == 0:
        return "business_error"  # Should not happen, but safe default

    stderr_lower = stderr.lower()

    # API/Token errors that should trigger circuit breaker
    api_error_patterns = [
        "rate limit",
        "rate_limit",
        "ratelimit",
        "token",
        "quota",
        "api error",
        "api_error",
        "apierror",
        "authentication",
        "auth_error",
        "unauthorized",
        "401",
        "403",
        "429",
        "insufficient_quota",
        "insufficient quota",
        "context length",
        "context_length",
        "max_tokens",
        "timeout waiting for",
    ]

    for pattern in api_error_patterns:
        if pattern in stderr_lower:
            return "api_error"

    # Business errors that should NOT trigger circuit breaker
    business_error_patterns = [
        "merge conflict",
        "merge_conflict",
        "test failed",
        "test_failed",
        "tests failed",
        "review rejected",
        "review_rejected",
        "build failed",
    ]

    for pattern in business_error_patterns:
        if pattern in stderr_lower:
            return "business_error"

    # Conservative: unknown errors count toward breaker
    return "unknown"


class CircuitBreaker:
    """Dispatch-level circuit breaker.

    Tracks consecutive failures from Dispatcher._run_command().
    When threshold is reached, blocks new dispatches until cooldown expires.

    State machine:
        CLOSED --[N failures]--> OPEN --[cooldown]--> HALF_OPEN
          ^                                            |
          +-------[success]----------------------------+
          +-------[failure]------> OPEN (reset cooldown)
    """

    def __init__(
        self,
        failure_threshold: int = 4,
        cooldown_seconds: int = 300,
        half_open_max_tests: int = 1,
    ) -> None:
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_tests = half_open_max_tests
        self._half_open_tests: int = 0

    def record_success(self) -> None:
        """Reset to CLOSED on any successful dispatch."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self._half_open_tests = 0

        if old_state != CircuitState.CLOSED:
            logger.bind(domain="orchestra", action="circuit_breaker").warning(
                f"Circuit breaker: {old_state.value} -> CLOSED"
            )

    def record_failure(self, error_category: ErrorCategory) -> None:
        """Increment failure counter. Transition to OPEN if threshold hit.

        Args:
            error_category: Classification of the failure
        """
        # Business errors don't count toward breaker
        if error_category == "business_error":
            return

        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failure during HALF_OPEN -> back to OPEN
            self.state = CircuitState.OPEN
            self._half_open_tests = 0
            logger.bind(domain="orchestra", action="circuit_breaker").warning(
                "Circuit breaker: HALF_OPEN -> OPEN (test failed)"
            )
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.bind(domain="orchestra", action="circuit_breaker").warning(
                    f"Circuit breaker: CLOSED -> OPEN "
                    f"(failures={self.failure_count}, "
                    f"threshold={self.failure_threshold})"
                )

    def allow_request(self) -> bool:
        """Check if dispatch is allowed.

        Returns:
            True if dispatch should proceed, False if blocked
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if cooldown expired
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                self._half_open_tests = 1  # Count this probe request
                logger.bind(domain="orchestra", action="circuit_breaker").warning(
                    "Circuit breaker: OPEN -> HALF_OPEN (cooldown expired)"
                )
                return True
            else:
                remaining = self.cooldown_seconds - int(elapsed)
                logger.bind(domain="orchestra", action="circuit_breaker").warning(
                    f"Circuit breaker OPEN, blocking dispatch ({remaining}s remaining)"
                )
                return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited test requests
            if self._half_open_tests < self.half_open_max_tests:
                self._half_open_tests += 1
                return True
            else:
                logger.bind(domain="orchestra", action="circuit_breaker").warning(
                    "Circuit breaker HALF_OPEN, max test requests reached"
                )
                return False

        return False

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._half_open_tests = 0
        logger.bind(domain="orchestra", action="circuit_breaker").info(
            "Circuit breaker manually reset to CLOSED"
        )

    @property
    def state_value(self) -> str:
        """Get current state as string for serialization."""
        return self.state.value

    @property
    def last_failure_timestamp(self) -> float | None:
        """Expose last failure timestamp if recorded."""
        return self.last_failure_time or None
