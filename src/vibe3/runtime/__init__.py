"""Runtime package.

Public interface for runtime components including circuit breaker,
heartbeat server, periodic check executors, and orchestra instance management.

This module serves as the unified public interface for runtime components.
Import from vibe3.runtime instead of external modules to ensure clean dependencies.
"""

from typing import TYPE_CHECKING

from vibe3.config.orchestra_config import PeriodicCheckConfig

# Module-level re-exports from models/ and config/ (safe, no cycle risk)
from vibe3.models.orchestra_config import OrchestraConfig

# Module-level re-exports from orchestra.logging (safe, no cycle risk)
from vibe3.orchestra.logging import (
    append_orchestra_event,
    append_orchestra_run_separator,
)

# Lazy imports via __getattr__ for everything else to avoid circular dependencies
if TYPE_CHECKING:
    from vibe3.runtime.circuit_breaker import (
        CircuitBreaker,
        CircuitState,
        ErrorCategory,
        classify_failure,
    )
    from vibe3.runtime.cleanup_executor import execute_expired_resource_cleanup
    from vibe3.runtime.heartbeat import HeartbeatServer
    from vibe3.runtime.orchestra_instance import (
        OrchestraInstanceInfo,
        read_instance_info,
        validate_instance,
        write_instance_info,
    )
    from vibe3.runtime.periodic_check_executor import execute_periodic_check
    from vibe3.runtime.service_protocol import ServiceBase
    from vibe3.services.error_tracking_service import ErrorTrackingService


def __getattr__(name: str) -> object:
    """Lazy import for all symbols to avoid circular dependencies.

    All symbols (runtime submodules, services) are imported lazily
    to prevent circular import issues.
    """
    # Orchestra instance management
    if name == "OrchestraInstanceInfo":
        from vibe3.runtime.orchestra_instance import OrchestraInstanceInfo

        return OrchestraInstanceInfo
    if name == "read_instance_info":
        from vibe3.runtime.orchestra_instance import read_instance_info

        return read_instance_info
    if name == "validate_instance":
        from vibe3.runtime.orchestra_instance import validate_instance

        return validate_instance
    if name == "write_instance_info":
        from vibe3.runtime.orchestra_instance import write_instance_info

        return write_instance_info

    # Runtime submodule symbols
    if name == "CircuitBreaker":
        from vibe3.runtime.circuit_breaker import CircuitBreaker

        return CircuitBreaker
    if name == "CircuitState":
        from vibe3.runtime.circuit_breaker import CircuitState

        return CircuitState
    if name == "ErrorCategory":
        from vibe3.runtime.circuit_breaker import ErrorCategory

        return ErrorCategory
    if name == "classify_failure":
        from vibe3.runtime.circuit_breaker import classify_failure

        return classify_failure
    if name == "execute_expired_resource_cleanup":
        from vibe3.runtime.cleanup_executor import execute_expired_resource_cleanup

        return execute_expired_resource_cleanup
    if name == "HeartbeatServer":
        from vibe3.runtime.heartbeat import HeartbeatServer

        return HeartbeatServer
    if name == "execute_periodic_check":
        from vibe3.runtime.periodic_check_executor import execute_periodic_check

        return execute_periodic_check
    if name == "ServiceBase":
        from vibe3.runtime.service_protocol import ServiceBase

        return ServiceBase

    # Services symbols (services/ may import from runtime)
    if name == "ErrorTrackingService":
        from vibe3.services.error_tracking_service import ErrorTrackingService

        return ErrorTrackingService

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    # Orchestra instance management
    "OrchestraInstanceInfo",
    "read_instance_info",
    "validate_instance",
    "write_instance_info",
    # External dependencies
    "OrchestraConfig",
    "PeriodicCheckConfig",
    "append_orchestra_event",
    "append_orchestra_run_separator",
    # Services (via __getattr__)
    "ErrorTrackingService",
]
