"""Orchestra service package - status aggregation and helpers.

Public API Contract:
- FlowOrchestratorService: Main orchestration service
- OrchestraStatusService, OrchestraSnapshot, IssueStatusEntry: Status management
- fetch_serve_status_data: Serve status utilities
- get_manager_usernames, get_handoff_state_label: Config utilities

All exports are part of the public API.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.config import (
        get_handoff_state_label,
        get_manager_usernames,
    )
    from vibe3.services.orchestra.orchestrator import FlowOrchestratorService
    from vibe3.services.orchestra.serve_status import fetch_serve_status_data
    from vibe3.services.orchestra.status import (
        IssueStatusEntry,
        OrchestraSnapshot,
        OrchestraStatusService,
        format_issue_runtime_line,
        format_issue_summary_line,
        is_running_issue,
    )

__all__ = [
    # From helpers
    "get_manager_usernames",
    "get_handoff_state_label",
    # From orchestrator
    "FlowOrchestratorService",
    # From serve_status
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
    # From helpers
    "get_manager_usernames": "vibe3.config",
    "get_handoff_state_label": "vibe3.config",
    # From orchestrator
    "FlowOrchestratorService": "vibe3.services.orchestra.orchestrator",
    # From serve_status
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
