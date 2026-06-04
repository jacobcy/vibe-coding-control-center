"""Adapter shell for backward compatibility.

Re-exports FlowManager from domain layer for legacy imports.
FlowManager is also available from its canonical location:
- vibe3.domain.flow_manager.FlowManager
"""

from vibe3.domain import FlowManager

__all__ = ["FlowManager"]
