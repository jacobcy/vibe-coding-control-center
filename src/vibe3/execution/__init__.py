"""Execution control plane public interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Cross-module imports (not self-references) - kept minimal per modularity rules
from vibe3.models import ExecutionLaunchResult, ExecutionRequest

if TYPE_CHECKING:
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.execution.codeagent_runner import CodeagentExecutionService
    from vibe3.execution.coordinator import ExecutionCoordinator
    from vibe3.execution.execution_lifecycle import (
        execution_prefix,
        persist_execution_lifecycle_event,
    )
    from vibe3.execution.governance_sync_runner import run_governance_sync
    from vibe3.execution.issue_role_sync_runner import (
        run_issue_role_async,
        run_issue_role_sync,
    )
    from vibe3.execution.noop_gate import apply_unified_noop_gate
    from vibe3.execution.session_service import load_session_id

# Lazy imports for self-references (avoid circular init dependencies)
_LAZY_IMPORTS = {
    "CapacityService": "vibe3.execution.capacity_service",
    "CodeagentExecutionService": "vibe3.execution.codeagent_runner",
    "ExecutionCoordinator": "vibe3.execution.coordinator",
    "execution_prefix": "vibe3.execution.execution_lifecycle",
    "persist_execution_lifecycle_event": "vibe3.execution.execution_lifecycle",
    "apply_unified_noop_gate": "vibe3.execution.noop_gate",
    "load_session_id": "vibe3.execution.session_service",
    "run_governance_sync": "vibe3.execution.governance_sync_runner",
    "run_issue_role_async": "vibe3.execution.issue_role_sync_runner",
    "run_issue_role_sync": "vibe3.execution.issue_role_sync_runner",
}


def __getattr__(name: str) -> object:
    """Lazy import for execution symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
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
    # Sync runners
    "run_governance_sync",
    "run_issue_role_async",
    "run_issue_role_sync",
]
