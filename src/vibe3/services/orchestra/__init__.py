"""Orchestra service package - status aggregation and helpers."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.orchestra.helpers import (
        get_handoff_state_label,
        get_manager_usernames,
    )
    from vibe3.services.orchestra.orchestrator import FlowOrchestratorService
    from vibe3.services.orchestra.status import (
        IssueStatusEntry,
        OrchestraSnapshot,
        OrchestraStatusService,
    )

__all__ = [
    # From helpers
    "get_manager_usernames",
    "get_handoff_state_label",
    # From orchestrator
    "FlowOrchestratorService",
    # From status
    "IssueStatusEntry",
    "OrchestraSnapshot",
    "OrchestraStatusService",
]

_SYMBOL_MODULES = {
    # From helpers
    "get_manager_usernames": "vibe3.services.orchestra.helpers",
    "get_handoff_state_label": "vibe3.services.orchestra.helpers",
    # From orchestrator
    "FlowOrchestratorService": "vibe3.services.orchestra.orchestrator",
    # From status
    "IssueStatusEntry": "vibe3.services.orchestra.status",
    "OrchestraSnapshot": "vibe3.services.orchestra.status",
    "OrchestraStatusService": "vibe3.services.orchestra.status",
}


def __getattr__(name: str) -> Any:
    """Lazy import for Orchestra services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.orchestra import OrchestraStatusService

    While avoiding circular imports at module load time.
    """
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
