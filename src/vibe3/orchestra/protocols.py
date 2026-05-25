"""Protocol definitions for orchestra layer dependency injection.

These Protocols (Ports) define abstract interfaces that allow the orchestra
layer to depend on abstractions rather than concrete implementations from
services/execution/roles, eliminating circular dependencies.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.models.orchestration import IssueInfo


@runtime_checkable
class FlowManagerPort(Protocol):
    """Abstract interface for flow management operations.

    This Protocol defines the operations that GlobalDispatchCoordinator and other
    orchestra components need from FlowManager, without depending on the concrete
    implementation.
    """

    # Attributes (Protocol treats these as required attributes on the concrete class)
    git: "GitClient"

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Find the latest flow for an issue, regardless of active status."""
        ...

    def create_flow_for_issue(self, issue: "IssueInfo") -> dict | None:
        """Create a new flow for an issue or return existing reusable flow."""
        ...

    def get_active_flow_count(self) -> int:
        """Count active flows that count toward capacity limit."""
        ...

    def get_pr_for_issue(self, issue_number: int) -> int | None:
        """Return the PR number associated with the issue's flow, or None."""
        ...
