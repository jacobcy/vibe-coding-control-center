"""Frozen-queue maintenance service for GlobalDispatchCoordinator.

Extracted from dispatch_coordinator.py to manage file size while keeping
queue lifecycle operations accessible from coordinate().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.config import get_manager_usernames
from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry
from vibe3.services.shared import (
    clear_queue_dirty,
    is_queue_dirty,
    should_skip_from_queue,
)
from vibe3.utils import resolve_milestone_rank, resolve_priority, resolve_roadmap_rank

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from vibe3.domain.protocols.dispatch_protocols import (
        QueuePersistenceServiceProtocol,
    )
    from vibe3.runtime import CheckServiceProtocol


class DispatchQueueMaintenanceService:
    """Queue lifecycle maintenance operations.

    Lightweight queue maintenance that avoids full GitHub API collections
    by operating on existing queue entries with local issue reloads.
    Used by GlobalDispatchCoordinator to keep its frozen queue up-to-date
    between full collection cycles.

    Each method takes queue state as input and returns updated state,
    with internal side-effects (persistence, PR cache) handled via
    injected service dependencies.
    """

    def __init__(
        self,
        config: OrchestraConfig,
        queue_persistence: QueuePersistenceServiceProtocol,
        load_issue: Callable[[int], IssueInfo | None],
        check_service: Callable[[], CheckServiceProtocol],
        supervisor_label: str,
        has_actionable: Callable[[], bool],
        has_pending_blocked: Callable[[], bool],
        has_qualifiable_blocked: Callable[[], bool],
        has_dispatchable_entries: Callable[[list[QueueEntry]], bool],
        merge_queue_fn: Callable[
            [list[QueueEntry], list[QueueEntry]], list[QueueEntry]
        ],
        should_collect_fn: Callable[[int], bool],
        collect_frozen_queue_fn: Callable[[], Awaitable[list[QueueEntry]]],
        emit_event: Callable[[str, str], None],
    ) -> None:
        self._config = config
        self._queue_persistence = queue_persistence
        self._load_issue = load_issue
        self._check_service_callable = check_service
        self._supervisor_label = supervisor_label
        self._has_actionable = has_actionable
        self._has_pending_blocked = has_pending_blocked
        self._has_qualifiable_blocked = has_qualifiable_blocked
        self._has_dispatchable_entries = has_dispatchable_entries
        self._merge_queue_fn = merge_queue_fn
        self._should_collect_fn = should_collect_fn
        self._collect_frozen_queue_fn = collect_frozen_queue_fn
        self._emit_event = emit_event

    def _invalidate_pr_cache(self) -> None:
        self._check_service_callable().invalidate_pr_cache()

    def _sync_queue_persistence_issue_loader(self) -> None:
        if hasattr(self._queue_persistence, "load_issue"):
            self._queue_persistence.load_issue = self._load_issue  # type: ignore[union-attr]

    def startup_restore(
        self, frozen_queue: list[QueueEntry] | None
    ) -> list[QueueEntry]:
        """Restore queue from persistence on cold start.

        Returns restored queue, or empty list if nothing to restore.
        """
        if frozen_queue is not None:
            return frozen_queue

        logger.bind(domain="global_dispatch", trigger="startup_restore").debug(
            "Restoring queue from persistence"
        )
        self._queue_persistence.frozen_queue = None
        self._sync_queue_persistence_issue_loader()
        restored = self._queue_persistence.restore()
        result = restored if restored is not None else []
        self._queue_persistence.frozen_queue = result
        self._invalidate_pr_cache()
        return result

    def promote_progressed(self, frozen_queue: list[QueueEntry]) -> list[QueueEntry]:
        """Promote state-changed entries to front; remove terminal entries.

        Returns updated queue.
        """
        logger.bind(domain="global_dispatch", trigger="promote_progressed").debug(
            "Promoting progressed entries"
        )
        self._queue_persistence.frozen_queue = frozen_queue
        self._sync_queue_persistence_issue_loader()
        cleared_all = self._queue_persistence.promote()
        if cleared_all:
            self._invalidate_pr_cache()
        result = self._queue_persistence.frozen_queue
        return result if result is not None else []

    def resort_existing(self, frozen_queue: list[QueueEntry]) -> list[QueueEntry]:
        """Re-sort existing queue entries without full collection.

        Lightweight queue maintenance that avoids GitHub API calls by
        using only local issue reloads. Removes stale entries, preserves
        waiting_state, and re-sorts non-waiting entries.

        Returns the updated queue.
        """
        if not frozen_queue:
            return frozen_queue

        logger.bind(domain="global_dispatch", trigger="resort_existing").debug(
            "Re-sorting existing queue entries"
        )

        waiting: list[QueueEntry] = []
        eligible: list[QueueEntry] = []
        eligible_issues: list[IssueInfo] = []

        for entry in frozen_queue:
            issue = self._load_issue(entry.issue_number)

            if issue is None:
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                    "from queue during resort (issue not found)",
                )
                continue

            if issue.state == IssueState.DONE:
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                    "from queue during resort (state terminal: done)",
                )
                continue

            if issue.state != IssueState.BLOCKED and should_skip_from_queue(
                issue,
                supervisor_label=self._supervisor_label,
                manager_usernames=get_manager_usernames(self._config),
                require_manager_assignee=True,
            ):
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{issue.number} "
                    "from queue during resort (supervisor or assignee check)",
                )
                continue

            if issue.state:
                entry.collected_state = issue.state.value

            if entry.waiting_state is not None:
                waiting.append(entry)
            else:
                eligible.append(entry)
                eligible_issues.append(issue)

        if eligible:
            state_order = {
                IssueState.REVIEW: 0,
                IssueState.MERGE_READY: 1,
                IssueState.IN_PROGRESS: 2,
                IssueState.CLAIMED: 3,
                IssueState.HANDOFF: 4,
                IssueState.READY: 5,
            }

            def _key(item: tuple[QueueEntry, IssueInfo]) -> tuple:
                e, issue = item
                s = (
                    IssueState(e.collected_state)
                    if e.collected_state
                    else IssueState.READY
                )
                sp = state_order.get(s, 99)
                md = (
                    {"title": issue.milestone, "number": 0} if issue.milestone else None
                )
                mr, _ = resolve_milestone_rank(md)
                rr, _ = resolve_roadmap_rank(issue.labels)
                p = resolve_priority(issue.labels)
                return (sp, mr, rr, -p, issue.number)

            pairs = list(zip(eligible, eligible_issues))
            pairs.sort(key=_key)
            eligible = [e for e, _ in pairs]

        result = waiting + eligible

        self._emit_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: resort existing complete, "
            f"total={len(result)} issues "
            f"(waiting={len(waiting)}, sorted={len(eligible)})",
        )
        return result

    async def scheduled_refresh(
        self,
        tick_id: int,
        frozen_queue: list[QueueEntry],
        dispatch_paused: bool,
    ) -> tuple[bool, list[QueueEntry], bool]:
        """Run scheduled full queue refresh if tick matches interval.

        Returns:
            Tuple of (was_refreshed, new_frozen_queue, new_dispatch_paused).
        """
        queue_refresh = self._config.queue_refresh
        if (
            tick_id > 0
            and queue_refresh.enabled
            and tick_id % queue_refresh.interval_ticks == 0
        ):
            logger.bind(
                domain="global_dispatch", trigger="scheduled_queue_refresh"
            ).debug("Running scheduled full queue refresh")
            fresh = await self._collect_frozen_queue_fn()
            self._invalidate_pr_cache()

            # Merge with existing queue to preserve waiting_state,
            # then check dispatchable entries using the same logic
            # as exhausted_refresh (commit aff68e917).
            merged = self._merge_queue_fn(frozen_queue or [], fresh)
            new_paused = not self._has_dispatchable_entries(merged)
            return True, merged, new_paused
        return False, frozen_queue, dispatch_paused

    def paused_blocked_check(
        self,
        dispatch_paused: bool,
    ) -> tuple[bool, bool, bool]:
        """Check paused state and re-qualify blocked entries.

        Returns:
            Tuple of (
                new_dispatch_paused,
                paused_with_pending_blocked,
                unpaused_for_qualifiable_blocked,
            ).
        """
        logger.bind(domain="global_dispatch", trigger="paused_blocked_check").debug(
            "Checking paused state and blocked entries"
        )
        if dispatch_paused:
            if self._has_actionable():
                return False, False, False
            if self._has_pending_blocked():
                if self._has_qualifiable_blocked():
                    return False, False, True
                return True, True, False
        return dispatch_paused, False, False

    async def exhausted_refresh(
        self,
        dispatched_count: int,
        queue_refreshed: bool,
        frozen_queue: list[QueueEntry],
        dispatch_paused: bool,
        *,
        unpaused_for_qualifiable_blocked: bool = False,
    ) -> tuple[list[QueueEntry], bool]:
        """Rebuild queue when actionable candidates are exhausted after dispatch.

        1. Trigger a full collection (which includes blocked-issue dependency
           check) via _collect_frozen_queue_fn.
        2. Merge fresh entries into the existing queue.  The merge function
           _merge_queue_fn keeps old entries with waiting_state for the same
           issue_numbers, so genuinely *new* work stays actionable
           (waiting_state=None) while duplicates of already-waiting entries do
           not.
        3. After the merge, check whether any entry in the merged queue is
           still actionable (waiting_state is None *and* collected_state !=
           'blocked').  If none are, the pool is truly exhausted — return
           dispatch_paused=True.

           Exception: when this tick just re-qualified a blocked entry, the
           collection may have changed remote state after building the fresh
           queue. Keep dispatch unpaused so the next tick can observe it.

        Returns:
            Tuple of (new_frozen_queue, new_dispatch_paused).
        """
        need_collect = not queue_refreshed and self._should_collect_fn(dispatched_count)
        if need_collect:
            logger.bind(domain="global_dispatch", trigger="queue_exhausted").debug(
                "Queue exhausted after dispatch, rebuilding for next tick"
            )
            self._emit_event(
                "dispatcher",
                "GlobalDispatchCoordinator: queue exhausted after dispatch, "
                "rebuilding for next tick",
            )
            fresh = await self._collect_frozen_queue_fn()
            self._invalidate_pr_cache()
            new_frozen_queue = self._merge_queue_fn(frozen_queue or [], fresh)

            # After merge, check if ANY entry is still dispatchable.
            # Merge preserves old entries with waiting_state for same issue_numbers,
            # so if all fresh entries are duplicates of existing waiting entries
            # or fail preflight, the merged queue should remain paused.
            has_dispatchable = self._has_dispatchable_entries(new_frozen_queue)
            if not has_dispatchable and not unpaused_for_qualifiable_blocked:
                self._emit_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: dispatch paused "
                    "(no actionable entries after collection and blocked check)",
                )
                return new_frozen_queue, True
            return new_frozen_queue, False

        # When collection was skipped (queue already refreshed this tick),
        # still re-verify the paused state.  scheduled_refresh uses
        # _has_dispatchable_entries which is a weaker check than the full
        # dispatch preflight run by _dispatch_loop.  An entry that passes
        # _has_dispatchable_entries may still fail dispatch preflight and
        # be removed from the queue.  If nothing was dispatched and the
        # queue now has no truly dispatchable entries, the pool is exhausted.
        if dispatched_count == 0 and queue_refreshed:
            has_dispatchable = self._has_dispatchable_entries(frozen_queue)
            if not has_dispatchable and dispatch_paused is False:
                self._emit_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: dispatch paused "
                    "(no actionable entries after queue cleanup)",
                )
                return frozen_queue, True
        return frozen_queue, dispatch_paused

    async def consume_queue_dirty_signal(
        self,
        frozen_queue: list[QueueEntry],
        *,
        dispatch_paused: bool = False,
    ) -> tuple[bool, list[QueueEntry], bool]:
        """Consume queue-dirty signal from external sources (e.g., CLI task resume).

        If the signal marker exists:
        1. Log with distinct trigger
        2. Clear the signal
        3. Emit orchestra event
        4. Resort existing queue to pick up resumed issues
        5. Fall back to full collection if resort finds no actionable entries

        Returns:
            Tuple of (signal_consumed, new_frozen_queue, new_dispatch_paused).
        """
        if not is_queue_dirty():
            return False, frozen_queue, dispatch_paused

        logger.bind(domain="global_dispatch", trigger="queue_dirty_signal").debug(
            "Queue dirty signal detected, consuming"
        )

        clear_queue_dirty()

        self._emit_event(
            "dispatcher",
            "GlobalDispatchCoordinator: queue dirty signal consumed",
        )

        try:
            # Resort existing queue to pick up resumed issues
            result = self.resort_existing(frozen_queue)
        except Exception:
            logger.bind(
                domain="global_dispatch",
                trigger="queue_dirty_signal",
            ).warning("Resort failed after dirty signal, returning unchanged queue")
            return True, frozen_queue, dispatch_paused

        # Check if resort found any actionable entries
        has_actionable = any(
            entry.waiting_state is None and entry.collected_state != "blocked"
            for entry in result
        )

        # If no actionable entries found, fall back to full collection
        if not has_actionable:
            logger.bind(
                domain="global_dispatch",
                trigger="queue_dirty_signal",
            ).debug(
                "Resort found no actionable entries, falling back to full collection"
            )
            self._emit_event(
                "dispatcher",
                "GlobalDispatchCoordinator: queue dirty signal: "
                "full collection fallback (resort found no actionable entries)",
            )
            try:
                result = await self._collect_frozen_queue_fn()
                self._invalidate_pr_cache()
            except Exception:
                logger.bind(
                    domain="global_dispatch",
                    trigger="queue_dirty_signal",
                ).warning(
                    "Full collection failed after dirty signal, "
                    "returning resort result"
                )
                return True, result, dispatch_paused

            # Check again if full collection found actionable entries
            has_actionable_after = any(
                entry.waiting_state is None and entry.collected_state != "blocked"
                for entry in result
            )

            if not has_actionable_after:
                self._emit_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: dispatch paused "
                    "(no actionable entries after queue dirty signal collection)",
                )
                return True, result, True

        return True, result, dispatch_paused
