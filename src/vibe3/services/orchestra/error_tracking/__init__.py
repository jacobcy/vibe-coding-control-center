"""Error tracking services for orchestra."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService

__all__ = ["ErrorTrackingService"]

_SYMBOL_MODULES = {
    "ErrorTrackingService": "vibe3.services.orchestra.error_tracking.service",
}


def __getattr__(name: str) -> Any:
    """Lazy import for error tracking symbols."""
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
