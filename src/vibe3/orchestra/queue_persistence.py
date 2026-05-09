"""Queue persistence operations for GlobalDispatchCoordinator.

Extracted from global_dispatch_coordinator.py to reduce LOC below CI block threshold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.orchestra.logging import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient

    from .global_dispatch_coordinator import QueueEntry

MAX_RETRY_COUNT = 3


class QueuePersistence:
    """Handles persistence operations for the frozen queue."""

    def __init__(self, store: SQLiteClient | None) -> None:
        self._store = store

    def load_persisted_queue(self) -> list[QueueEntry] | None:
        """Load persisted queue entries from SQLite."""
        if self._store is None:
            return None

        try:
            persisted = self._store.load_queue_entries()
            if persisted:
                # Import here to avoid circular dependency
                from .global_dispatch_coordinator import QueueEntry

                queue = [
                    QueueEntry(
                        issue_number=entry["issue_number"],
                        collected_state=entry["collected_state"],
                        waiting_state=entry["waiting_state"],
                        retry_count=entry["retry_count"],
                    )
                    for entry in persisted
                ]
                logger.bind(domain="global_dispatch").info(
                    f"Loaded {len(queue)} queue entries from persistence"
                )
                return queue
        except Exception as exc:
            logger.bind(domain="global_dispatch").error(
                f"Failed to load persisted queue: {exc}"
            )
        return None

    def persist_queue_entries(self, queue: list[QueueEntry]) -> None:
        """Persist all queue entries to SQLite."""
        if self._store is None or not queue:
            return
        try:
            for entry in queue:
                self._store.save_queue_entry(
                    issue_number=entry.issue_number,
                    collected_state=entry.collected_state or "",
                    waiting_state=entry.waiting_state,
                    retry_count=entry.retry_count,
                )
        except Exception as exc:
            logger.bind(domain="global_dispatch").error(
                f"Failed to persist queue entries: {exc}"
            )

    def update_persisted_entry(self, entry: QueueEntry) -> None:
        """Update a single queue entry in SQLite."""
        if self._store is None:
            return
        try:
            self._store.save_queue_entry(
                issue_number=entry.issue_number,
                collected_state=entry.collected_state or "",
                waiting_state=entry.waiting_state,
                retry_count=entry.retry_count,
            )
        except Exception as exc:
            logger.bind(domain="global_dispatch", issue=entry.issue_number).error(
                f"Failed to update persisted entry: {exc}"
            )

    def remove_persisted_entry(self, issue_number: int) -> None:
        """Remove a queue entry from SQLite."""
        if self._store is None:
            return
        try:
            self._store.remove_queue_entry(issue_number)
        except Exception as exc:
            logger.bind(domain="global_dispatch", issue=issue_number).error(
                f"Failed to remove persisted entry: {exc}"
            )

    def check_retry_threshold(self, queue: list[QueueEntry]) -> list[QueueEntry]:
        """Remove entries exceeding MAX_RETRY_COUNT.

        Returns:
            List of entries removed from the queue.
        """
        if self._store is None or not queue:
            return []

        removed: list[QueueEntry] = []
        try:
            exceeders = self._store.get_queue_entries_over_retry_limit(MAX_RETRY_COUNT)
            for issue_number in exceeders:
                # Find and remove the entry
                entry = next((e for e in queue if e.issue_number == issue_number), None)
                if entry:
                    removed.append(entry)
                    # Remove from persistence
                    self._store.remove_queue_entry(issue_number)
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: removed #{issue_number} "
                        f"from queue (retry_count > {MAX_RETRY_COUNT})",
                    )
                    logger.bind(domain="global_dispatch", issue=issue_number).warning(
                        f"Removed issue #{issue_number} from queue "
                        f"(retry threshold exceeded)"
                    )
        except Exception as exc:
            logger.bind(domain="global_dispatch").error(
                f"Failed to check retry threshold: {exc}"
            )

        return removed
