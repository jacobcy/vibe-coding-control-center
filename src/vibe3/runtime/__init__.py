"""Runtime package.

Public interface for runtime components including circuit breaker,
heartbeat server, periodic check executors, and orchestra instance management.
"""

from typing import TYPE_CHECKING

# Lazy imports via __getattr__ for everything to avoid circular dependencies
if TYPE_CHECKING:
    from vibe3.runtime.circuit_breaker import (
        CircuitBreaker,
        CircuitState,
        ErrorCategory,
        classify_failure,
    )
    from vibe3.runtime.cleanup_executor import execute_expired_resource_cleanup
    from vibe3.runtime.heartbeat import FailedGateProtocol, HeartbeatServer
    from vibe3.runtime.orchestra_instance import (
        OrchestraInstanceInfo,
        read_instance_info,
        validate_instance,
        write_instance_info,
    )
    from vibe3.runtime.periodic_check_executor import execute_periodic_check
    from vibe3.runtime.service_protocol import ServiceBase
    from vibe3.runtime.taxonomy import MODULE_CATEGORY_MAP, ModuleCategory


def __getattr__(name: str) -> object:
    """Lazy import for all symbols to avoid circular dependencies.

    All symbols are imported lazily to prevent circular import issues.
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
    if name == "FailedGateProtocol":
        from vibe3.runtime.heartbeat import FailedGateProtocol

        return FailedGateProtocol
    if name == "execute_periodic_check":
        from vibe3.runtime.periodic_check_executor import execute_periodic_check

        return execute_periodic_check
    if name == "ServiceBase":
        from vibe3.runtime.service_protocol import ServiceBase

        return ServiceBase

    # Taxonomy symbols
    if name == "MODULE_CATEGORY_MAP":
        from vibe3.runtime.taxonomy import MODULE_CATEGORY_MAP

        return MODULE_CATEGORY_MAP
    if name == "ModuleCategory":
        from vibe3.runtime.taxonomy import ModuleCategory

        return ModuleCategory

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "ErrorCategory",
    "classify_failure",
    "execute_expired_resource_cleanup",
    "HeartbeatServer",
    "FailedGateProtocol",
    "execute_periodic_check",
    "ServiceBase",
    "OrchestraInstanceInfo",
    "read_instance_info",
    "validate_instance",
    "write_instance_info",
    # Taxonomy (via __getattr__)
    "MODULE_CATEGORY_MAP",
    "ModuleCategory",
]
