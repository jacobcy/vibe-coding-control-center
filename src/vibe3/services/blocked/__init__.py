"""Blocked state management services."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.blocked.types import (
        BlockedState,
        ConsistencyReport,
        UnblockResult,
    )

__all__ = [
    "BlockedState",
    "ConsistencyReport",
    "UnblockResult",
]

_SYMBOL_MODULES = {
    "BlockedState": "vibe3.services.blocked.types",
    "ConsistencyReport": "vibe3.services.blocked.types",
    "UnblockResult": "vibe3.services.blocked.types",
}


def __getattr__(name: str) -> Any:
    """Lazy import for blocked state symbols."""
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
