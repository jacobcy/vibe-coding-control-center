"""Runtime package.

Public interface for runtime components including circuit breaker,
heartbeat server, and periodic check executors.
"""

from vibe3.runtime.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    ErrorCategory,
    classify_failure,
)
from vibe3.runtime.cleanup_executor import execute_expired_resource_cleanup
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.runtime.periodic_check_executor import execute_periodic_check
from vibe3.runtime.service_protocol import ServiceBase

__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    "CircuitState",
    "ErrorCategory",
    "classify_failure",
    # Cleanup executor
    "execute_expired_resource_cleanup",
    # Heartbeat server
    "HeartbeatServer",
    # Periodic check executor
    "execute_periodic_check",
    # Service protocol
    "ServiceBase",
]
