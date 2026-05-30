"""Protocol definitions for dispatch coordination."""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vibe3.models.orchestration import IssueInfo
    from vibe3.orchestra.queue_entry import QueueEntry


class IssueCollectionServiceProtocol(Protocol):
    """Protocol for issue collection service."""

    def collect_open_issues(self, limit: int = 100) -> list["IssueInfo"]:
        """Collect open issues from GitHub.

        Args:
            limit: Maximum number of issues to collect

        Returns:
            List of normalized IssueInfo objects
        """
        ...


class QueuePersistenceServiceProtocol(Protocol):
    """Protocol for queue persistence."""

    frozen_queue: list["QueueEntry"] | None

    def persist(self) -> None:
        """Persist queue state."""
        ...

    def restore(self) -> list["QueueEntry"] | None:
        """Restore queue state.

        Returns:
            Restored queue entries or None
        """
        ...

    def get_queued_issue_numbers(self) -> set[int]:
        """Get the set of issue numbers currently in the frozen queue.

        Returns:
            Set of issue numbers in queue
        """
        ...

    def promote(self) -> bool:
        """Move progressed issues to the front; remove blocked/failed from queue.

        Returns:
            True if all entries were removed (queue cleared), False otherwise.
        """
        ...


class DispatchHealthCheckProtocol(Protocol):
    """Protocol for dispatch health checks."""

    def check_issue_health(self, issue: "IssueInfo") -> bool:
        """Check if issue is healthy for dispatch.

        Args:
            issue: Issue to check

        Returns:
            True if issue can be dispatched (healthy or transient error)
            False if issue should be skipped (genuine failure or terminal state)
        """
        ...
