"""Flow protocols — interfaces for flow state access.

Defines Protocol interfaces for reading and writing flow state,
decoupling consumers (environment, orchestra) from the concrete
FlowService implementation in the services layer.

Import paths:
    # Recommended (explicit source)
    from vibe3.clients.protocols.flow import FlowReader, FlowStatePort

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from vibe3.models import FlowState


class FlowReader(Protocol):
    """Read-only protocol for flow state queries used by orchestra services."""

    def get_flow_for_issue(self, issue_number: int) -> dict[str, Any] | None:
        """Return the active flow record for the given issue, or None."""
        ...

    def get_pr_for_issue(self, issue_number: int) -> int | None:
        """Return the PR number associated with the issue's flow, or None."""
        ...

    def get_active_flow_count(self) -> int:
        """Return the number of currently active flows."""
        ...


class FlowStatePort(Protocol):
    """Minimal protocol for flow state read/write used by environment layer.

    Decouples the environment module (layer 5) from the concrete FlowService
    (layer 3) by defining only the methods environment needs. The concrete
    FlowService satisfies this protocol via its FlowReadMixin and
    FlowWriteMixin methods.
    """

    def get_flow_state(self, branch: str) -> FlowState | None:
        """Return FlowState for the given branch, or None if not found."""
        ...

    def update_flow_metadata(self, branch: str, **updates: Any) -> None:
        """Update flow metadata fields for the given branch."""
        ...


__all__ = ["FlowReader", "FlowStatePort"]
