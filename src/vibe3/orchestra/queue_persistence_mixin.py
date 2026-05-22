"""Queue persistence mixin for GlobalDispatchCoordinator.

Handles frozen queue persistence, restoration, and promotion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_operations import promote_progressed_entries
from vibe3.services.label_utils import should_skip_from_queue

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.models.orchestra_config import OrchestraConfig
    from vibe3.services.check_service import CheckService


@dataclass
class QueueEntry:
    """Frozen queue entry tracked only by issue identity and wait state."""

    issue_number: int
    collected_state: str | None = None
    waiting_state: str | None = None


class QueuePersistenceMixin:
    """Mixin providing queue persistence and restoration for coordinators.

    Note: This mixin expects the following attributes/methods to be available
    on the parent class:
    - _frozen_queue: list[QueueEntry] | None
    - _store: SQLiteClient
    - _config: OrchestraConfig
    - _github: GitHubClient
    - _registry: SessionRegistryService | None
    - _supervisor_label: str
    - _check_service: object | None
    - _load_issue(issue_number: int) -> IssueInfo | None
    - _poll_issues_by_state(state: IssueState) -> Coroutine[Any, Any, list[IssueInfo]]
    """

    # Type annotations for mypy (actual attributes provided by parent class)
    if TYPE_CHECKING:
        _frozen_queue: list[QueueEntry] | None
        _store: "SQLiteClient"
        _config: "OrchestraConfig"
        _github: "GitHubClient"
        _registry: "SessionRegistryService | None"
        _supervisor_label: str
        _check_service: "CheckService | None"

        # Methods (declared as attributes for mixin pattern)
        _load_issue: Callable[[int], IssueInfo | None]
        _poll_issues_by_state: Callable[
            [IssueState], Coroutine[Any, Any, list[IssueInfo]]
        ]

    def _restore_queue(self) -> list[QueueEntry] | None:
        """Load persisted queue from database on restart."""
        try:
            entries = self._store.load_frozen_queue()
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
            issue = self._load_issue(issue_number)

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
                supervisor_label=self._supervisor_label,
                manager_usernames=self._config.get_manager_usernames(),
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
            self._store.remove_from_frozen_queue(issue_number)

        logger.bind(domain="global_dispatch").info(
            f"Restored {len(restored)} queue entries from persistence "
            f"(removed {len(invalid_issue_numbers)} invalid entries)"
        )

        return restored if restored else None

    def _persist_queue(self) -> None:
        """Persist current frozen queue to database."""
        frozen_queue = getattr(self, "_frozen_queue", None)
        if frozen_queue is None:
            self._store.clear_frozen_queue()
            return

        entries = [
            {
                "issue_number": e.issue_number,
                "collected_state": e.collected_state,
                "waiting_state": e.waiting_state,
            }
            for e in frozen_queue
        ]
        self._store.save_frozen_queue(entries)

    def get_queued_issue_numbers(self) -> set[int]:
        """Get the set of issue numbers currently in the frozen queue."""
        frozen_queue = getattr(self, "_frozen_queue", None)
        if not frozen_queue:
            return set()
        return {e.issue_number for e in frozen_queue}

    def _promote_progressed_entries(self) -> None:
        """Move progressed issues to the front; remove blocked/failed from queue."""
        frozen_queue = getattr(self, "_frozen_queue", None)
        if not frozen_queue:
            return

        # Convert QueueEntry to dict for helper function
        queue_dicts = [
            {
                "issue_number": e.issue_number,
                "collected_state": e.collected_state,
                "waiting_state": e.waiting_state,
            }
            for e in frozen_queue
        ]

        promoted, retained, removed = promote_progressed_entries(
            queue_dicts,
            self._config,
            self._github,
            self._registry,
            self._supervisor_label,
            load_issue_func=self._load_issue,
        )

        # Convert back to QueueEntry
        promoted_entries = [
            QueueEntry(
                issue_number=e["issue_number"],
                collected_state=e.get("collected_state"),
                waiting_state=e.get("waiting_state"),
            )
            for e in promoted
        ]

        retained_entries = [
            QueueEntry(
                issue_number=e["issue_number"],
                collected_state=e.get("collected_state"),
                waiting_state=e.get("waiting_state"),
            )
            for e in retained
        ]

        # Update frozen queue
        if promoted_entries or retained_entries:
            self._frozen_queue = promoted_entries + retained_entries
        else:
            # All entries removed - trigger fresh collection
            self._frozen_queue = None
            self._check_service = None  # Invalidate when queue is set to None

        # Persist the updated queue state
        self._persist_queue()

    async def _collect_frozen_queue(self) -> list[QueueEntry]:
        """Collect a new frozen queue only when the current one is empty."""
        queue: list[QueueEntry] = []
        seen_issue_numbers: set[int] = set()
        append_orchestra_event(
            "dispatcher",
            "GlobalDispatchCoordinator: starting queue collection",
        )
        for state in (
            IssueState.REVIEW,
            IssueState.MERGE_READY,
            IssueState.IN_PROGRESS,
            IssueState.CLAIMED,
            IssueState.HANDOFF,
            IssueState.BLOCKED,
            IssueState.READY,
        ):
            try:
                issues = await self._poll_issues_by_state(state)
                for issue in issues:
                    if issue.number in seen_issue_numbers:
                        continue
                    seen_issue_numbers.add(issue.number)
                    queue.append(
                        QueueEntry(
                            issue_number=issue.number,
                            collected_state=state.value,
                        )
                    )
            except Exception as exc:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: collect_ready_issues failed for "
                    f"{state.value}: {exc}",
                )
                logger.bind(
                    domain="global_dispatch",
                    state=state.value,
                ).error(f"poll_issues_by_state failed for {state.value}: {exc}")
        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: queue collection complete, "
            f"total={len(queue)} issues",
        )
        return queue
