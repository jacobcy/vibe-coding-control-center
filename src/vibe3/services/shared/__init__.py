"""Shared utilities and services for vibe3."""

from typing import Any

__all__ = [
    # Will be populated as files are migrated
]

_SYMBOL_MODULES: dict[str, str] = {}


def __getattr__(name: str) -> Any:
    """Lazy import for shared utilities to avoid circular dependencies."""
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
