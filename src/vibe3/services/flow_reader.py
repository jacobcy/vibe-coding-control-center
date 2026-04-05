"""FlowReader Protocol — read-only interface for flow state queries.

Defines the minimal read interface that OrchestraStatusService needs,
decoupling orchestra from the manager implementation layer.
"""

from __future__ import annotations

from typing import Any, Protocol


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
