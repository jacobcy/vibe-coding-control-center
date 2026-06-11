"""Frozen-queue dispatch coordinator.

Migrated from orchestra/global_dispatch_coordinator.py to establish
domain-first architecture.

Queue strategy:
1. Keep queued issues resident across ticks
2. Rebuild when actionable active entries are exhausted
3. Give blocked-only rebuilds one dispatch-time qualify pass
4. If candidates remain blocked, pause recollection until work changes
5. Capacity still gates actual dispatch intents
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable, cast

from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.domain.protocols.dispatch_protocols import (
    CapacityServiceProtocol,
    CheckServiceProtocol,
    FlowContextResolverProtocol,
    FlowServiceProtocol,
    IssueCollectionServiceProtocol,
    IssueLoaderProtocol,
    LabelDispatchCallable,
    QueuePersistenceServiceProtocol,
    QueueSelectorProtocol,
)
from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
from vibe3.domain.publisher import publish
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.domain.role_resolver import find_role_for_state
from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry
from vibe3.observability import append_orchestra_event, get_degraded_manager
from vibe3.services import (
    IssueCollectionService,
    clean_old_state_labels,
    get_manager_usernames,
    should_skip_from_queue,
)

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

    def _sync_queue_persistence_issue_loader(self) -> None:
        """Keep queue persistence aligned with the coordinator issue loader."""
        if hasattr(self._queue_persistence, "load_issue"):
            self._queue_persistence.load_issue = self._load_issue

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
        """Collect a new frozen queue only when the current one is empty."""
        queue: list[QueueEntry] = []
        seen_issue_numbers: set[int] = set()
        append_orchestra_event(
            "dispatcher",
            "GlobalDispatchCoordinator: starting queue collection",
        )
        try:
            collected_issues = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                self._issue_collector_factory().collect_open_issues,
            )
        except Exception as exc:
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: collect_open_issues failed: {exc}",
            )
            logger.bind(domain="global_dispatch").error(
                f"collect_open_issues failed: {exc}"
            )
            collected_issues = []

        for state in (
            IssueState.REVIEW,
            IssueState.MERGE_READY,
            IssueState.IN_PROGRESS,
            IssueState.CLAIMED,
            IssueState.HANDOFF,
            IssueState.READY,
        ):
            try:
                issues = self._queue_selector(
                    collected_issues,
                    state,
                    self._config,
                    self._github,
                    self._store,
                    self._flow_manager,
                    self._qualify_gate,
                    self._supervisor_label,
                    queue_filter=self._queue_filter,
                )
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
                ).error(
                    "select_ready_issues_from_collected_issues failed for "
                    f"{state.value}: {exc}"
                )
        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: queue collection complete, "
            f"total={len(queue)} issues",
        )
        return queue

    def _check_dispatch_health(self, issue: IssueInfo) -> bool:
        """Pre-dispatch health check. Returns True if issue can be dispatched.

        Delegates structural checks to CheckService, with terminal state
        and transient error handling inlined directly in this method.
        """
        branch, _ = self._flow_context(issue.number)

        # Empty-branch guard: fail-open only for manager entry states
        if not branch:
            issue_state = issue.state
            if issue_state not in {IssueState.READY, IssueState.HANDOFF}:
                state_value = issue_state.value if issue_state else "unknown"
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: skipped #{issue.number} "
                    f"(missing flow context for {state_value})",
                )
                return False
            return True

        result = self._check_service.verify_branch(branch)

        flow_state = self._store.get_flow_state(branch)
        flow_status = (
            flow_state.get("flow_status", "active") if flow_state else "active"
        )

        # Terminal state: skip dispatch cleanly
        if flow_status in ("done", "aborted", "stale", "review"):
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: skipped #{issue.number} "
                f"(flow is {flow_status})",
            )
            return False

        if not result.is_valid:
            # Transient errors: fail-open
            transient_errors = ["Cannot verify", "No flow record"]
            is_transient = any(
                any(err.startswith(prefix) for err in result.issues)
                for prefix in transient_errors
            )
            if is_transient:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: fail-open for #{issue.number} "
                    f"(transient: {', '.join(result.issues)})",
                )
                return True

            # Genuine failure: block and skip
            reason = f"Health check failed: {', '.join(result.issues)}"
            block_succeeded = False
            try:
                self._flow_blocker.block_flow(
                    branch=branch, reason=reason, actor="orchestra:dispatcher"
                )
                block_succeeded = True
            except Exception as exc:
                logger.bind(domain="orchestra", action="health_check").warning(
                    f"Failed to block flow for #{issue.number}: {exc}"
                )
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: block_failed #{issue.number} "
                    f"(error: {exc}, health check: {reason})",
                )

            if block_succeeded:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: blocked #{issue.number} "
                    f"(health check failed: {reason})",
                )
            return False

        return True

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

    def _should_collect_after_dispatch(self, dispatched_count: int) -> bool:
        """Whether this tick should rebuild active queue candidates."""
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
                )
                return dispatched_count

            entry = self._frozen_queue[index]
            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
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
                )
                self._frozen_queue.pop(index)
                continue

            if issue.state == IssueState.DONE:
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

            # For BLOCKED issues: run qualify gate at intent time.
            # If qualify_blocked_issue returns None (still blocked per body truth),
            # the issue is popped from the current frozen queue cycle.
            # It may be re-collected on the next queue rebuild if it still has
            # the state/blocked label.
            if issue.state == IssueState.BLOCKED:
                target_state = self._qualify_gate.qualify_blocked_issue(issue)

                # Check degraded mode immediately after qualification
                degraded = get_degraded_manager()
                if degraded.is_degraded():
                    degraded_reason = degraded.get_reason()
                    reason_value = degraded_reason.value if degraded_reason else None
                    logger.bind(
                        domain="orchestra",
                        action="collect_blocked_intents",
                        degraded_mode=True,
                        reason=reason_value,
                        issue_number=issue.number,
                    ).warning(f"Qualification of #{issue.number} entered degraded mode")

                # Then check target_state
                if target_state is None:
                    self._frozen_queue.pop(index)
                    continue

                role = find_role_for_state(target_state)
                if role is None:
                    self._frozen_queue.pop(index)
                    continue
                entry.collected_state = target_state.value
            else:
                role = find_role_for_state(issue.state)
                if role is None:
                    self._frozen_queue.pop(index)
                    continue

            # === Pre-dispatch health check ===
            if not self._check_dispatch_health(issue):
                self._frozen_queue.pop(index)
                continue

            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatch-intent{reset} "
                f"#{issue.number} ({role.registry_role})",
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
            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatch-intent="
                f"{dispatched_count}{reset}",
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
        # Step 1: Restore queue from persistence if None
        if self._frozen_queue is None:
            self._queue_persistence.frozen_queue = None
            self._sync_queue_persistence_issue_loader()
            restored = self._queue_persistence.restore()
            self._frozen_queue = restored if restored is not None else []
            self._queue_persistence.frozen_queue = self._frozen_queue
            # Invalidate PR cache on restore to ensure fresh PR state
            self._check_service.invalidate_pr_cache()

        # Step 2: Promote progressed entries (state changes)
        self._queue_persistence.frozen_queue = self._frozen_queue
        self._sync_queue_persistence_issue_loader()
        cleared_all = self._queue_persistence.promote()
        if cleared_all:
            # Invalidate PR cache when queue is cleared
            self._check_service.invalidate_pr_cache()
        self._frozen_queue = self._queue_persistence.frozen_queue

        # Normalize after promotion: promote() may set
        # frozen_queue = None when all entries are removed
        if self._frozen_queue is None:
            self._frozen_queue = []

        queue_refreshed = False
        periodic_check = self._config.periodic_check
        if (
            tick_id > 0
            and periodic_check.enabled
            and tick_id % periodic_check.interval_ticks == 0
        ):
            fresh = await self._collect_frozen_queue()
            self._check_service.invalidate_pr_cache()
            self._dispatch_paused = bool(
                fresh and all(entry.collected_state == "blocked" for entry in fresh)
            )
            self._frozen_queue = fresh
            queue_refreshed = True

        paused_with_pending_blocked = False

        # Step 3: Paused mode waits for human task resume to create a
        # non-blocked candidate again. Keep existing waiting entries resident.
        # Blocked-only rebuilds get one dispatch-time qualify pass before the
        # coordinator enters a quiet paused state.
        if self._dispatch_paused:
            if self._has_actionable_entries():
                self._dispatch_paused = False
            elif self._has_pending_blocked_entries():
                if self._has_qualifiable_blocked_entries():
                    # A blocked entry can be dispatched now — unpause to let it through
                    self._dispatch_paused = False
                else:
                    paused_with_pending_blocked = True

        # Step 4: Dispatch actionable entries FIRST
        # Note: dispatch event logging is handled by _dispatch_loop internally
        dispatched_count = self._dispatch_loop(tick_id)

        # Step 5: Persist queue state AFTER dispatch but BEFORE collection.
        # Entries that were dispatched this tick have been popped (blocked entries
        # that failed qualify_gate are removed). Entries skipped due to capacity
        # limits remain in the queue and are persisted as-is.
        # Freshly collected entries from Step 6 are NOT included in this snapshot.
        self._queue_persistence.frozen_queue = self._frozen_queue
        self._queue_persistence.persist()

        # Step 5b: Early-exit when paused with only non-qualifiable blocked entries.
        # Skip collection — it would fetch the same all-blocked result again and
        # immediately re-enter the paused state, wasting GitHub API quota.
        if paused_with_pending_blocked:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: dispatch paused "
                "(blocked entries pending, no qualifiable candidates"
                " — skipping collection)",
            )
            return

        # Step 6: Rebuild active candidates once active queue is exhausted.
        need_collect = not queue_refreshed and self._should_collect_after_dispatch(
            dispatched_count
        )
        if need_collect:
            fresh = await self._collect_frozen_queue()
            # Invalidate PR cache after fresh collection
            self._check_service.invalidate_pr_cache()
            if fresh and all(entry.collected_state == "blocked" for entry in fresh):
                self._dispatch_paused = True
                self._frozen_queue = self._merge_queue(self._frozen_queue or [], fresh)
                append_orchestra_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: dispatch paused "
                    "(rebuild found only blocked issues)",
                )
            else:
                self._dispatch_paused = False
                self._frozen_queue = self._merge_queue(self._frozen_queue or [], fresh)
