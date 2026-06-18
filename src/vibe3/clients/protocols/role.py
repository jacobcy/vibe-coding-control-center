"""Protocol for TriggerableRoleDefinition used by services layer.

Moved from domain.protocols to clients.protocols to break circular dependency:
services.label_utils → domain.protocols

This is a read-only interface, appropriate for L6 clients layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vibe3.models import IssueState


class TriggerableRoleDefinitionProtocol(Protocol):
    """Protocol for TriggerableRoleDefinition used by services.label_utils."""

    @property
    def trigger_name(self) -> str:
        """Trigger name for this role (e.g., 'manager', 'plan', 'run')."""
        ...

    @property
    def trigger_state(self) -> "IssueState":
        """Issue state that triggers this role (e.g., IssueState.READY)."""
        ...


__all__ = ["TriggerableRoleDefinitionProtocol"]
