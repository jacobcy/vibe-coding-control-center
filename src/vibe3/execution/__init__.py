"""Execution control plane public interface."""

from typing import TYPE_CHECKING, Any

from vibe3.models import ExecutionLaunchResult, ExecutionRequest

if TYPE_CHECKING:
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.execution.codeagent_runner import CodeagentExecutionService
    from vibe3.execution.coordinator import ExecutionCoordinator
    from vibe3.execution.execution_lifecycle import (
        execution_prefix,
        persist_execution_lifecycle_event,
    )
    from vibe3.execution.noop_gate import apply_unified_noop_gate
    from vibe3.execution.session_service import load_session_id


def __getattr__(name: str) -> Any:
    """Lazy import for all symbols to avoid circular dependencies."""
    if name == "CapacityService":
        from vibe3.execution.capacity_service import CapacityService

        return CapacityService
    if name == "CodeagentExecutionService":
        from vibe3.execution.codeagent_runner import CodeagentExecutionService

        return CodeagentExecutionService
    if name == "ExecutionCoordinator":
        from vibe3.execution.coordinator import ExecutionCoordinator

        return ExecutionCoordinator
    if name == "execution_prefix":
        from vibe3.execution.execution_lifecycle import execution_prefix

        return execution_prefix
    if name == "persist_execution_lifecycle_event":
        from vibe3.execution.execution_lifecycle import (
            persist_execution_lifecycle_event,
        )

        return persist_execution_lifecycle_event
    if name == "apply_unified_noop_gate":
        from vibe3.execution.noop_gate import apply_unified_noop_gate

        return apply_unified_noop_gate
    if name == "load_session_id":
        from vibe3.execution.session_service import load_session_id

        return load_session_id

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core services
    "ExecutionCoordinator",
    "CodeagentExecutionService",
    "CapacityService",
    # Request/Result contracts
    "ExecutionRequest",
    "ExecutionLaunchResult",
    # Lifecycle utilities
    "execution_prefix",
    "persist_execution_lifecycle_event",
    "load_session_id",
    # Gates
    "apply_unified_noop_gate",
]
