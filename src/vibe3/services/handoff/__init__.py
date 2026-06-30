"""Handoff domain services subpackage.

Public API Contract:
- HandoffService: Main handoff service
- HandoffStatusService: Status tracking
- HandoffStorage: Storage operations
- resolve_handoff_target: Resolution utilities

All exports are part of the public API.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.handoff.resolution import resolve_handoff_target
    from vibe3.services.handoff.service import HandoffService
    from vibe3.services.handoff.status import HandoffStatusService
    from vibe3.services.handoff.storage import HandoffStorage

__all__ = [
    "HandoffService",
    "HandoffStatusService",
    "HandoffStorage",
    "resolve_handoff_target",
]

_SYMBOL_MODULES = {
    "HandoffService": "vibe3.services.handoff.service",
    "HandoffStatusService": "vibe3.services.handoff.status",
    "HandoffStorage": "vibe3.services.handoff.storage",
    "resolve_handoff_target": "vibe3.services.handoff.resolution",
}


def __getattr__(name: str) -> Any:
    """Lazy import for Handoff services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.handoff import HandoffStorage, resolve_handoff_target

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
