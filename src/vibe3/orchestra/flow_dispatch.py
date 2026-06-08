"""Adapter shell for backward compatibility.

Re-exports FlowManager from domain layer for legacy imports.
FlowManager is also available from its canonical location:
- vibe3.domain.flow_manager.FlowManager
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.domain import FlowManager


def __getattr__(name: str) -> object:
    if name == "FlowManager":
        from vibe3.domain import FlowManager

        return FlowManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["FlowManager"]
