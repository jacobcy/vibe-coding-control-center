"""Flow-related protocols for domain layer.

Migrated from orchestra/protocols.py to establish domain-first architecture.
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.models import IssueInfo


class FlowManagerProtocol(Protocol):
    """Protocol for flow manager operations (external consumer interface).

    This protocol exposes only the methods used by external consumers,
    not the internal service dependencies of FlowManager.
    """

    git: "GitClient"

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Find the latest flow for an issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            Flow dict if found, None otherwise
        """
        ...

    def create_flow_for_issue(self, issue: "IssueInfo") -> dict | None:
        """Create a new flow for an issue.

        Args:
            issue: IssueInfo object

        Returns:
            Flow dict if created, None otherwise
        """
        ...
