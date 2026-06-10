"""Error tracking services for orchestra."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # No public exports yet

__all__: list[str] = []

_SYMBOL_MODULES: dict[str, str] = {}


def __getattr__(name: str) -> Any:
    """Lazy import for error tracking symbols."""
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
