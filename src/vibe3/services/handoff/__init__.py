"""Handoff domain services subpackage.

Public API Contract:
- HandoffService: Main handoff service
- HandoffStatusService, HandoffStatusResult: Status tracking
- HandoffStorage: Storage operations
- resolve_handoff_target, is_shared_handoff_ref, to_display_target: Resolution utilities
- validate_authoritative_ref: Validation utilities

All exports are part of the public API.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.handoff.resolution import (
        is_shared_handoff_ref,
        resolve_handoff_target,
        to_display_target,
    )
    from vibe3.services.handoff.service import HandoffService
    from vibe3.services.handoff.status import (
        HandoffStatusResult,
        HandoffStatusService,
    )
    from vibe3.services.handoff.storage import HandoffStorage
    from vibe3.services.handoff.validation import validate_authoritative_ref

__all__ = [
    # Classes - service
    "HandoffService",
    # Classes - status
    "HandoffStatusService",
    "HandoffStatusResult",
    # Classes - storage
    "HandoffStorage",
    # Functions - resolution
    "resolve_handoff_target",
    "is_shared_handoff_ref",
    "to_display_target",
    # Functions - validation
    "validate_authoritative_ref",
]

_SYMBOL_MODULES = {
    # Classes - service
    "HandoffService": "vibe3.services.handoff.service",
    # Classes - status
    "HandoffStatusService": "vibe3.services.handoff.status",
    "HandoffStatusResult": "vibe3.services.handoff.status",
    # Classes - storage
    "HandoffStorage": "vibe3.services.handoff.storage",
    # Functions - resolution
    "resolve_handoff_target": "vibe3.services.handoff.resolution",
    "is_shared_handoff_ref": "vibe3.services.handoff.resolution",
    "to_display_target": "vibe3.services.handoff.resolution",
    # Functions - validation
    "validate_authoritative_ref": "vibe3.services.handoff.validation",
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
