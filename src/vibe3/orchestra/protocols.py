"""Protocol definitions for orchestra layer."""

from typing import Protocol

from vibe3.clients.git_client import GitClient
from vibe3.orchestra.queue_entry import QueueEntry


class FlowManagerPort(Protocol):
    """Protocol for flow management operations.

    Used for dependency injection in GlobalDispatchCoordinator to decouple
    from concrete FlowManager implementation. Enables testability via
    structural typing — any object with matching attributes satisfies this.
    """

    git: GitClient

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Get flow context for an issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            Flow context dict or None if no flow found
        """
        ...


class QueuePersistencePort(Protocol):
    """Protocol for queue persistence operations.

    Used for dependency injection in GlobalDispatchCoordinator to decouple
    from concrete QueuePersistenceService implementation.
    """

    frozen_queue: list[QueueEntry] | None

    def restore(self) -> list[QueueEntry] | None:
        """Load persisted queue from database on restart.

        Returns:
            Restored queue entries or None if restore failed
        """
        ...

    def persist(self) -> None:
        """Persist current frozen queue to database."""
        ...

    def promote(self) -> bool:
        """Promote progressed queue entries.

        Returns:
            True if promotion succeeded
        """
        ...

    def get_queued_issue_numbers(self) -> set[int]:
        """Get set of queued issue numbers.

        Returns:
            Set of issue numbers currently in queue
        """
        ...
