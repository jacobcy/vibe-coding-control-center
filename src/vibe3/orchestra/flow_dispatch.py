"""Adapter shell for backward compatibility.

Re-exports FlowManager from domain layer for legacy imports.
FlowManager is also available from its canonical location:
- vibe3.domain.flow_manager.FlowManager
"""

import importlib

__all__ = ["FlowManager"]  # noqa: F822


def __getattr__(name: str) -> object:
    """Lazy import for backward compatibility symbols."""
    if name == "FlowManager":
        return getattr(importlib.import_module("vibe3.domain"), "FlowManager")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
