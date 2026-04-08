"""Agent resolver for orchestra roles (backward compatibility layer).

This module re-exports functions from runtime layer for backward compatibility.
"""

from vibe3.runtime.agent_resolver import (
    _resolve_and_sync,
    resolve_governance_agent_options,
    resolve_manager_agent_options,
    resolve_supervisor_agent_options,
)

__all__ = [
    "_resolve_and_sync",
    "resolve_governance_agent_options",
    "resolve_manager_agent_options",
    "resolve_supervisor_agent_options",
]
