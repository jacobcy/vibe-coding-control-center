"""Queue persistence service for GlobalDispatchCoordinator.

Handles frozen queue persistence, restoration, and promotion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.models import IssueInfo, IssueState
from vibe3.models.queue_entry import QueueEntry
from vibe3.orchestra.queue_operations import promote_progressed_entries
from vibe3.services.label_utils import should_skip_from_queue
from vibe3.services.orchestra_helpers import get_manager_usernames

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.models.orchestra_config import OrchestraConfig


@dataclass
class QueuePersistenceService:
    """Service providing queue persistence and restoration.

    This service handles restore, persist, and promote operations for the
    frozen queue. Collection logic remains on the coordinator (it does GitHub
    API polling, not persistence).
    """

    store: "SQLiteClient"
    config: "OrchestraConfig"
    github: "GitHubClient"
    registry: "SessionRegistryService | None"
    supervisor_label: str
    load_issue: Callable[[int], IssueInfo | None]
    frozen_queue: list[QueueEntry] | None = None

    def restore(self) -> list[QueueEntry] | None:
        """Load persisted queue from database on restart."""
        try:
            entries = self.store.load_frozen_queue()
        except Exception as exc:
            logger.bind(domain="global_dispatch").warning(
                f"Failed to load persisted queue: {exc}"
            )
            return None

        if not entries:
            return None

        restored: list[QueueEntry] = []
        invalid_issue_numbers: list[int] = []

        for entry in entries:
            issue_number = entry["issue_number"]
            issue = self.load_issue(issue_number)

            # Skip invalid issues (not found)
            if issue is None:
                invalid_issue_numbers.append(issue_number)
                continue

            # Skip DONE issues
            if issue.state == IssueState.DONE:
                invalid_issue_numbers.append(issue_number)
                continue

            # Skip supervisor-labeled issues
            if should_skip_from_queue(
                issue,
                supervisor_label=self.supervisor_label,
                manager_usernames=get_manager_usernames(self.config),
                require_manager_assignee=True,
            ):
                invalid_issue_numbers.append(issue_number)
                continue

            # Restore entry, resetting waiting_state so they are re-dispatched
            restored.append(
                QueueEntry(
                    issue_number=issue_number,
                    collected_state=entry.get("collected_state"),
                    waiting_state=None,  # Reset to trigger re-dispatch
                )
            )

        # Clean up invalid entries from database
        for issue_number in invalid_issue_numbers:
            self.store.remove_from_frozen_queue(issue_number)

        logger.bind(domain="global_dispatch").info(
            f"Restored {len(restored)} queue entries from persistence "
            f"(removed {len(invalid_issue_numbers)} invalid entries)"
        )

        return restored if restored else None

    def persist(self) -> None:
        """Persist current frozen queue to database."""
        if self.frozen_queue is None:
            self.store.clear_frozen_queue()
            return

        entries = [
            {
                "issue_number": e.issue_number,
                "collected_state": e.collected_state,
                "waiting_state": e.waiting_state,
            }
            for e in self.frozen_queue
        ]
        self.store.save_frozen_queue(entries)

    def get_queued_issue_numbers(self) -> set[int]:
        """Get the set of issue numbers currently in the frozen queue."""
        if not self.frozen_queue:
            return set()
        return {e.issue_number for e in self.frozen_queue}

    def promote(self) -> bool:
        """Move progressed issues to the front; remove blocked/failed from queue.

        Returns:
            True if all entries were removed (queue cleared), False otherwise.
        """
        if not self.frozen_queue:
            return False

        promoted, retained, _removed = promote_progressed_entries(
            self.frozen_queue,
            self.config,
            self.github,
            self.registry,
            self.supervisor_label,
            load_issue_func=self.load_issue,
        )

        # Update frozen queue
        if promoted or retained:
            self.frozen_queue = promoted + retained
            return False
        else:
            # All entries removed - trigger fresh collection
            self.frozen_queue = None
            return True  # Signal that queue was cleared
