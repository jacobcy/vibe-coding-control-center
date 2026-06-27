"""Orchestra service package - status aggregation and helpers.

Public API Contract:
- FlowOrchestratorService: Main orchestration service
- OrchestraStatusService, OrchestraSnapshot, IssueStatusEntry: Status management
- ErrorTrackingService: Error tracking service
- record_error, record_dispatch_failure_if_unexpected: Error recording wrappers
- fetch_serve_status_data: Serve status utilities

All exports are part of the public API.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.orchestra.coordination import CoordinationResolver
    from vibe3.services.orchestra.error_projection import build_error_projection_hook
    from vibe3.services.orchestra.error_recording import (
        record_dispatch_failure_if_unexpected,
        record_error,
    )
    from vibe3.services.orchestra.error_tracking import ErrorTrackingService
    from vibe3.services.orchestra.orchestrator import FlowOrchestratorService
    from vibe3.services.orchestra.serve_status import (
        ServeStatusService,
        fetch_serve_status_data,
    )
    from vibe3.services.orchestra.status import (
        IssueStatusEntry,
        OrchestraSnapshot,
        OrchestraStatusService,
        format_issue_runtime_line,
        format_issue_summary_line,
        is_running_issue,
    )

__all__ = [
    # From error_projection
    "build_error_projection_hook",
    # From error_recording
    "record_error",
    "record_dispatch_failure_if_unexpected",
    # From orchestrator
    "CoordinationResolver",
    "ErrorTrackingService",
    "FlowOrchestratorService",
    # From serve_status
    "ServeStatusService",
    "fetch_serve_status_data",
    # From status
    "IssueStatusEntry",
    "OrchestraSnapshot",
    "OrchestraStatusService",
    "format_issue_runtime_line",
    "format_issue_summary_line",
    "is_running_issue",
]

_SYMBOL_MODULES = {
    # From error_projection
    "build_error_projection_hook": "vibe3.services.orchestra.error_projection",
    # From error_recording
    "record_error": "vibe3.services.orchestra.error_recording",
    "record_dispatch_failure_if_unexpected": "vibe3.services.orchestra.error_recording",
    # From orchestrator
    "CoordinationResolver": "vibe3.services.orchestra.coordination",
    "ErrorTrackingService": "vibe3.services.orchestra.error_tracking",
    "FlowOrchestratorService": "vibe3.services.orchestra.orchestrator",
    # From serve_status
    "ServeStatusService": "vibe3.services.orchestra.serve_status",
    "fetch_serve_status_data": "vibe3.services.orchestra.serve_status",
    # From status
    "IssueStatusEntry": "vibe3.services.orchestra.status",
    "OrchestraSnapshot": "vibe3.services.orchestra.status",
    "OrchestraStatusService": "vibe3.services.orchestra.status",
    "format_issue_runtime_line": "vibe3.services.orchestra.status",
    "format_issue_summary_line": "vibe3.services.orchestra.status",
    "is_running_issue": "vibe3.services.orchestra.status",
}


def __getattr__(name: str) -> Any:
    """Lazy import for Orchestra services symbols to avoid circular dependencies."""
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
