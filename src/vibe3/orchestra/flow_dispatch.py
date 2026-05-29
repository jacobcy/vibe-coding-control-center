"""Adapter shell for backward compatibility.

Re-exports FlowManager from domain layer.
This module will be deprecated in a future version.
"""

from vibe3.domain.flow_manager import FlowManager

__all__ = ["FlowManager"]
