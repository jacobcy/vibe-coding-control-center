"""Frozen-queue dispatch coordinator.

Migrated from orchestra/global_dispatch_coordinator.py to establish
domain-first architecture.

Queue strategy:
1. Keep queued issues resident across ticks
2. Rebuild when actionable active entries are exhausted
3. Give blocked-only rebuilds one dispatch-time qualify pass
4. If candidates remain blocked, pause recollection until work changes
5. Capacity still gates actual dispatch intents
6. Every collection re-qualifies BLOCKED issues (see
   _requalify_blocked_issues) so resolved blockers get relabeled and
   picked up on the next pass
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable, cast

from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.config import get_manager_usernames
from vibe3.domain import publish
from vibe3.domain.dispatch_health import DispatchHealthService
from vibe3.domain.dispatch_preflight import (
    DispatchPreflightDecision,
    DispatchPreflightService,
)
from vibe3.domain.dispatch_queue_collection import (
    DispatchQueueCollectionService,
)
from vibe3.domain.dispatch_queue_maintenance import (
    DispatchQueueMaintenanceService,
)
from vibe3.domain.protocols.dispatch_protocols import (
    CapacityServiceProtocol,
    FlowContextResolverProtocol,
    FlowServiceProtocol,
    IssueCollectionServiceProtocol,
    IssueLoaderProtocol,
    LabelDispatchCallable,
    QueuePersistenceServiceProtocol,
    QueueSelectorProtocol,
)
from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.domain.role_resolver import find_role_for_state
from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry
from vibe3.observability import append_orchestra_event
from vibe3.runtime import CheckServiceProtocol
from vibe3.services.issue import IssueCollectionService
from vibe3.services.shared import clean_old_state_labels, should_skip_from_queue

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.environment import SessionRegistryService
    from vibe3.roles import TriggerableRoleDefinition

# Hard limit to prevent extreme tick duration in edge cases
MAX_INTENTS_PER_TICK = 10


class GlobalDispatchCoordinator:
    """Frozen queue with state-change requeue semantics."""

    _config: OrchestraConfig
    _capacity: CapacityServiceProtocol
    _github: GitHubClient
    _store: "SQLiteClient"
    _flow_manager: FlowManagerProtocol
    _registry: "SessionRegistryService | None"
    _executor: ThreadPoolExecutor
    _owns_executor: bool
    _frozen_queue: list[QueueEntry] | None
    _flow_blocker: FlowServiceProtocol
    _queue_persistence: QueuePersistenceServiceProtocol
    _load_issue: IssueLoaderProtocol
    _flow_context: FlowContextResolverProtocol
    _queue_selector: QueueSelectorProtocol
    _check_service: CheckServiceProtocol
    _issue_collector_factory: Callable[[], IssueCollectionServiceProtocol]
    _label_dispatcher: LabelDispatchCallable
    _dispatch_paused: bool
    _supervisor_label: str
    _remote_check_runner: Callable[[], None] | None
    _remote_check_interval: int
    _last_remote_check_tick: int
    _dispatch_health: DispatchHealthService
    _dispatch_preflight: DispatchPreflightService
    _current_tick_id: int

    def __init__(
        self,
        config: OrchestraConfig,
        capacity: CapacityServiceProtocol,
        github: GitHubClient,
        store: "SQLiteClient",
        flow_manager: FlowManagerProtocol,
        registry: "SessionRegistryService | None" = None,
        executor: ThreadPoolExecutor | None = None,
        *,
        flow_blocker: FlowServiceProtocol,
        queue_persistence: QueuePersistenceServiceProtocol,
        issue_loader: IssueLoaderProtocol,
        flow_context_resolver: FlowContextResolverProtocol,
        queue_selector: QueueSelectorProtocol,
        check_service: CheckServiceProtocol,
        issue_collector_factory: (
            Callable[[], IssueCollectionServiceProtocol] | None
        ) = None,
        label_dispatcher: LabelDispatchCallable | None = None,
        queue_filter: Callable[..., bool] | None = None,
        remote_check_runner: Callable[[], None] | None = None,
        remote_check_interval: int = 20,
    ) -> None:
        self._config = config
        self._capacity = capacity
        self._github = github
        self._store = store
        self._flow_manager = flow_manager
        self._registry = registry
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows
        )
        self._owns_executor = executor is None
        self._frozen_queue: list[QueueEntry] | None = None
        self._qualify_gate = QualifyGateService(config, github, store, flow_manager)

        # Injected runtime services
        self._flow_blocker = flow_blocker
        self._queue_persistence = queue_persistence
        self._load_issue = issue_loader
        self._flow_context = flow_context_resolver
        self._queue_selector = queue_selector
        self._check_service = check_service

        # Fallback: create default factory or use default dispatcher
        self._issue_collector_factory: Callable[[], IssueCollectionServiceProtocol] = (
            issue_collector_factory
            or (lambda: IssueCollectionService(github, config.repo))
        )

        # Lazy default for label_dispatcher to avoid module-level import
        if label_dispatcher is None:
            from vibe3.roles import build_label_dispatch_event

            self._label_dispatcher: LabelDispatchCallable = build_label_dispatch_event  # type: ignore[assignment]
        else:
            self._label_dispatcher = label_dispatcher

        self._dispatch_paused = False
        self._supervisor_label = config.supervisor_handoff.issue_label
        self._queue_filter = queue_filter
        self._remote_check_runner = remote_check_runner
        self._remote_check_interval = remote_check_interval
        self._last_remote_check_tick: int = 0
        self._current_tick_id: int = 0

        def _emit(category: str, message: str, *, color: str | None = None) -> None:
            append_orchestra_event(category, message, color=color)

        self._dispatch_health = DispatchHealthService(
            check_service=lambda: self._check_service,
            store=store,
            flow_blocker=flow_blocker,
            flow_context=lambda issue_number: self._flow_context(issue_number),
            emit_event=_emit,
        )
        self._dispatch_preflight = DispatchPreflightService(
            qualify_gate=self._qualify_gate,
            flow_context=lambda issue_number: self._flow_context(issue_number),
            structural_check=lambda issue: self._check_dispatch_health(issue),
        )

        self._queue_maintenance = DispatchQueueMaintenanceService(
            config=config,
            queue_persistence=queue_persistence,
            load_issue=issue_loader,
            check_service=lambda: self._check_service,
            supervisor_label=config.supervisor_handoff.issue_label,
            has_actionable=lambda: self._has_actionable_entries(),
            has_pending_blocked=lambda: self._has_pending_blocked_entries(),
            has_qualifiable_blocked=lambda: self._has_qualifiable_blocked_entries(),
            has_dispatchable_entries=lambda entries: self._has_dispatchable_entries(
                entries
            ),
            merge_queue_fn=lambda existing, fresh: self._merge_queue(existing, fresh),
            should_collect_fn=lambda count, tick_id=0: (  # type: ignore[misc]
                self._should_collect_after_dispatch(count)
            ),
            collect_frozen_queue_fn=lambda: self._collect_frozen_queue(),
            emit_event=_emit,
        )

        self._queue_collection = DispatchQueueCollectionService(
            config=config,
            github=github,
            store=store,
            flow_manager=flow_manager,
            executor=self._executor,
            issue_collector_factory=lambda: self._issue_collector_factory(),
            queue_selector=lambda *a, **kw: self._queue_selector(*a, **kw),
            qualify_gate=self._qualify_gate,
            supervisor_label=config.supervisor_handoff.issue_label,
            emit_event=_emit,
            queue_filter=queue_filter,
        )

        # Queue is lazily restored on first coordinate() call
        # (not eagerly in __init__ to avoid startup I/O and keep
        # coordinate() as the single queue-lifecycle owner)

    def shutdown(self) -> None:
        """Shutdown the executor if we own it."""
        if self._owns_executor and self._executor:
            self._executor.shutdown(wait=True)

    def get_queued_issue_numbers(self) -> set[int]:
        """Get the set of issue numbers currently in the frozen queue."""
        self._queue_persistence.frozen_queue = self._frozen_queue
        return self._queue_persistence.get_queued_issue_numbers()

    def _emit_dispatch_intent(
        self, role: "TriggerableRoleDefinition", issue: IssueInfo, tick_id: int = 0
    ) -> None:
        """Emit dispatch intent for an issue.

        Args:
            role: Triggerable role definition
            issue: Issue info
            tick_id: Heartbeat tick number for error tracking
        """

        # Pre-dispatch cleanup: remove conflicting state/* labels
        clean_old_state_labels(issue, role, self._config)

        branch, _ = self._flow_context(issue.number)
        from vibe3.domain.events.base import DomainEvent

        publish(
            cast(
                DomainEvent,
                self._label_dispatcher(role, issue, branch=branch, tick_id=tick_id),
            )
        )

    async def _collect_frozen_queue(self) -> list[QueueEntry]:
        """Full frozen queue collection delegating to DispatchQueueCollectionService."""
        return await self._queue_collection.collect_frozen_queue()

    def _check_dispatch_health(self, issue: IssueInfo) -> bool:
        """Pre-dispatch health check. Returns True if issue can be dispatched."""
        return self._dispatch_health.check(issue)

    def _run_dispatch_preflight(self, issue: IssueInfo) -> DispatchPreflightDecision:
        """Run the unified pre-dispatch gate for one issue."""
        return self._dispatch_preflight.evaluate(issue)

    def _merge_queue(
        self,
        existing: list[QueueEntry],
        fresh: list[QueueEntry],
    ) -> list[QueueEntry]:
        """Merge fresh entries into existing queue, deduplicating by issue_number.

        If same issue_number exists in both, keep the existing entry
        (to preserve waiting_state).

        Args:
            existing: Current queue entries (may have waiting_state set)
            fresh: Freshly collected entries (waiting_state is None)

        Returns:
            Merged queue with all unique issue_numbers
        """
        existing_numbers = {e.issue_number for e in existing}
        merged = list(existing)
        for entry in fresh:
            if entry.issue_number not in existing_numbers:
                merged.append(entry)
        return merged

    def _has_actionable_entries(self) -> bool:
        """Whether queue still has dispatchable active entries."""
        return bool(
            self._frozen_queue
            and any(
                entry.waiting_state is None and entry.collected_state != "blocked"
                for entry in self._frozen_queue
            )
        )

    def _has_pending_blocked_entries(self) -> bool:
        """Whether queue still has blocked entries that have not been re-qualified."""
        return bool(
            self._frozen_queue
            and any(
                entry.waiting_state is None and entry.collected_state == "blocked"
                for entry in self._frozen_queue
            )
        )

    def _has_qualifiable_blocked_entries(self) -> bool:
        """Whether any blocked queue entry would pass the qualify gate right now.

        Short-circuits on first qualifiable entry. Only called when already in
        paused state, so the per-entry qualify calls are cheaper than a full
        GitHub collection.
        """
        if not self._frozen_queue:
            return False
        for entry in self._frozen_queue:
            if entry.waiting_state is None and entry.collected_state == "blocked":
                issue = self._load_issue(entry.issue_number)
                if issue is None:
                    continue
                if self._qualify_gate.qualify_blocked_issue(issue) is not None:
                    return True
        return False

    def _has_dispatchable_entries(self, entries: list[QueueEntry]) -> bool:
        """Whether entries contain work that can pass dispatch preflight.

        Excludes aborted flows to prevent pool exhaustion detection interference.
        Aborted flows are allowed through health checks for recovery opportunities,
        but should not count as "dispatchable" for pool exhaustion purposes.
        """
        for entry in entries:
            if entry.waiting_state is not None or entry.collected_state == "blocked":
                continue

            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None or issue.state == IssueState.DONE:
                continue

            # Exclude aborted flows from dispatchable count
            _, flow_state = self._flow_context(issue.number)
            if flow_state and flow_state.get("flow_status") == "aborted":
                continue

            if issue.state != IssueState.BLOCKED and should_skip_from_queue(
                issue,
                supervisor_label=self._supervisor_label,
                manager_usernames=get_manager_usernames(self._config),
                require_manager_assignee=True,
            ):
                continue

            preflight = self._run_dispatch_preflight(issue)
            if preflight.allowed and preflight.target_state is not None:
                if find_role_for_state(preflight.target_state) is not None:
                    return True
        return False

    def _should_collect_after_dispatch(self, dispatched_count: int) -> bool:
        """Whether this tick should rebuild active queue candidates.

        Sleep mode behavior:
        - When dispatch is paused (sleep mode), skip collection except on wake-up ticks
        - Wake-up ticks occur every sleep_check_interval_ticks to check for new work
        - On wake-up ticks, allow collection to re-verify and maintain the paused state

        Normal mode behavior:
        - If already paused, this shouldn't happen (sleep mode covers this)
        - If capacity full, skip collection (no slots available)
        - If dispatched enough, skip collection (max intents reached)
        - Otherwise collect if no actionable entries remain
        """
        # Sleep mode: skip collection except on wake-up ticks
        if self._dispatch_paused:
            interval = self._config.pool_exhaustion.sleep_check_interval_ticks
            return self._current_tick_id % interval == 0

        status = self._capacity.get_capacity_status("manager")
        available_slots = status["remaining"]
        if available_slots <= 0:
            return False

        max_intents = min(available_slots, MAX_INTENTS_PER_TICK)
        if dispatched_count >= max_intents:
            return False

        return not self._has_actionable_entries()

    def _dispatch_loop(self, tick_id: int = 0) -> int:
        """Run dispatch loop against frozen queue.

        This method extracts the dispatch logic from coordinate() into a
        separate method for better readability and testability.

        Args:
            tick_id: Current tick number from heartbeat (default: 0)

        Returns:
            Number of issues dispatched in this tick
        """
        if not self._frozen_queue:
            return 0

        status = self._capacity.get_capacity_status("manager")
        available_slots = status["remaining"]

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: capacity full",
                color="yellow",
            )
            return 0

        # Apply hard limit: cap dispatches per tick regardless of capacity
        max_intents = min(available_slots, MAX_INTENTS_PER_TICK)

        dispatched_count = 0
        index = 0
        while index < len(self._frozen_queue):
            if dispatched_count >= max_intents:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
                    f"skipped remaining (capacity or hard limit reached)",
                    color="yellow",
                )
                return dispatched_count

            entry = self._frozen_queue[index]
            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                    "from queue (issue not found or state missing)",
                    color="yellow",
                )
                self._frozen_queue.pop(index)
                continue

            if issue.state != IssueState.BLOCKED and should_skip_from_queue(
                issue,
                supervisor_label=self._supervisor_label,
                manager_usernames=get_manager_usernames(self._config),
                require_manager_assignee=True,
            ):
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{issue.number} "
                    "from queue (supervisor or assignee check failed)",
                    color="yellow",
                )
                self._frozen_queue.pop(index)
                continue

            if issue.state == IssueState.DONE:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{issue.number} "
                    "from queue (state terminal: done)",
                )
                self._frozen_queue.pop(index)
                continue

            entry.collected_state = issue.state.value

            if entry.waiting_state is not None:
                index += 1
                continue

            # Per-issue active session gate
            if self._registry is not None:
                active = self._registry.get_live_sessions_for_issue(
                    issue_number=entry.issue_number,
                    roles=["manager", "planner", "executor", "reviewer"],
                )
                if active:
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: skipped #{entry.issue_number} "
                        f"(active session: role={active[0].get('role')})",
                    )
                    index += 1
                    continue

            preflight = self._run_dispatch_preflight(issue)
            if not preflight.allowed or preflight.target_state is None:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{issue.number} "
                    f"from queue (preflight failed: {preflight.reason})",
                )
                self._frozen_queue.pop(index)
                continue

            role = find_role_for_state(preflight.target_state)
            if role is None:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{issue.number} "
                    f"from queue (no role for state {preflight.target_state})",
                    color="yellow",
                )
                self._frozen_queue.pop(index)
                continue
            entry.collected_state = preflight.target_state.value

            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: dispatch-intent "
                f"#{issue.number} ({role.registry_role})",
                color="green",
            )
            self._emit_dispatch_intent(role, issue, tick_id)
            entry.waiting_state = entry.collected_state
            dispatched_count += 1

            logger.bind(
                domain="global_dispatch",
                role=role.registry_role,
                issue=issue.number,
            ).info(
                f"Emitted dispatch intent for #{issue.number} "
                f"({role.registry_role})"
            )
            index += 1

        if dispatched_count > 0:
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: dispatch-intent={dispatched_count}",
                color="green",
            )

        return dispatched_count

    async def coordinate(self, tick_id: int = 0) -> None:
        """Run one heartbeat tick against the frozen queue.

        Args:
            tick_id: Current tick number from heartbeat (default: 0)

        Queue Collection Strategy:
            Only collect fresh queue when actionable (non-blocked) candidates
            are exhausted AFTER dispatch. This avoids wasted GitHub API calls.
        """
        # Store tick_id for sleep mode wake-up checks
        self._current_tick_id = tick_id

        # Step 1: Restore from persistence on cold start
        self._queue_startup_restore()

        # Step 2: Promote state-changed entries
        self._queue_promote_progressed()

        # Step 2.5: Re-sort existing entries without full collection
        self._queue_resort_existing()

        # Step 2.5: Periodic remote check (before collection)
        if (
            self._remote_check_runner
            and tick_id - self._last_remote_check_tick >= self._remote_check_interval
        ):
            try:
                self._remote_check_runner()
            except Exception as exc:
                logger.bind(domain="check", action="remote").warning(
                    f"Remote check failed: {exc}"
                )
            finally:
                self._last_remote_check_tick = tick_id

        # Step 2.6: Consume queue-dirty signal from external sources
        # (e.g., CLI task resume)
        _dirty_consumed, self._frozen_queue, self._dispatch_paused = (
            await self._queue_maintenance.consume_queue_dirty_signal(
                self._frozen_queue or [],
                dispatch_paused=self._dispatch_paused,
            )
        )

        # Step 3: Periodic full refresh
        queue_refreshed, self._frozen_queue, self._dispatch_paused = (
            await self._queue_maintenance.scheduled_refresh(
                tick_id, self._frozen_queue or [], self._dispatch_paused
            )
        )

        # Step 4: Paused mode blocked re-qualification
        (
            self._dispatch_paused,
            paused_with_pending_blocked,
            unpaused_for_qualifiable_blocked,
        ) = self._queue_maintenance.paused_blocked_check(self._dispatch_paused)

        # Step 5: Dispatch actionable entries
        dispatched_count = self._dispatch_loop(tick_id)

        # Step 6: Persist queue state
        self._queue_persistence.frozen_queue = self._frozen_queue
        self._queue_persistence.persist()

        # Step 7: Early-exit when paused with only non-qualifiable blocked
        if paused_with_pending_blocked:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: dispatch paused "
                "(blocked entries pending, no qualifiable candidates"
                " — skipping collection)",
                color="yellow",
            )
            return

        # Step 8: Rebuild when candidates exhausted
        self._frozen_queue, self._dispatch_paused = (
            await self._queue_maintenance.exhausted_refresh(
                dispatched_count,
                queue_refreshed,
                self._frozen_queue or [],
                self._dispatch_paused,
                tick_id=tick_id,
                unpaused_for_qualifiable_blocked=unpaused_for_qualifiable_blocked,
            )
        )

    def is_dispatch_paused(self) -> bool:
        """Check if dispatch is paused due to exhausted pool.

        Returns:
            True if dispatch is paused (only blocked issues in queue)
        """
        return self._dispatch_paused

    # Shim methods: delegate to DispatchQueueMaintenanceService for
    # backward compatibility with existing tests that call these directly.

    def _queue_startup_restore(self) -> None:
        self._queue_maintenance._load_issue = self._load_issue  # type: ignore[union-attr]
        self._frozen_queue = self._queue_maintenance.startup_restore(self._frozen_queue)

    def _queue_promote_progressed(self) -> None:
        self._queue_maintenance._load_issue = self._load_issue  # type: ignore[union-attr]
        self._frozen_queue = self._queue_maintenance.promote_progressed(
            self._frozen_queue or []
        )

    def _queue_resort_existing(self) -> None:
        self._queue_maintenance._load_issue = self._load_issue  # type: ignore[union-attr]
        self._frozen_queue = self._queue_maintenance.resort_existing(
            self._frozen_queue or []
        )
