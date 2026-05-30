"""Queue-related protocols for domain layer.

Defines interfaces for queue management services,
enabling domain layer to use queue operations without
depending on orchestra implementation.
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vibe3.models.orchestration import IssueInfo


class QueueEntryProtocol(Protocol):
    """Protocol for queue entry data structure."""

    issue_number: int
    state: str
    role: str
    enqueued_at: str


class DispatchHealthCheckProtocol(Protocol):
    """Protocol for dispatch health check service."""

    def check_issue_health(self, issue: "IssueInfo") -> bool:
        """Check if issue is healthy for dispatch.

        Args:
            issue: Issue to check

        Returns:
            True if issue is healthy
        """
        ...


class IssueCollectionServiceProtocol(Protocol):
    """Protocol for issue collection service."""

    def collect_open_issues(self) -> list["IssueInfo"]:
        """Collect open issues from GitHub.

        Returns:
            List of open issues
        """
        ...


class QueuePersistenceProtocol(Protocol):
    """Protocol for queue persistence service."""

    def persist(self, queue_data: dict) -> None:
        """Persist queue state to storage.

        Args:
            queue_data: Queue state to persist
        """
        ...

    def restore(self) -> dict | None:
        """Restore queue state from storage.

        Returns:
            Restored queue state or None
        """
        ...
