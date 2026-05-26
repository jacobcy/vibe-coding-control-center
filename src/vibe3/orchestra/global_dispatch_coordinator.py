"""Frozen-queue dispatch coordinator.

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
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.domain import publish
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.observability.degraded_mode import get_degraded_manager
from vibe3.orchestra.issue_loader import (
    find_role_for_state,
    get_flow_context,
    load_issue,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.protocols import FlowManagerPort, QueuePersistencePort
from vibe3.orchestra.queue_entry import QueueEntry
from vibe3.orchestra.queue_operations import (
    collect_raw_issues_without_qualify,
    select_ready_issues,
)
from vibe3.roles.registry import build_label_dispatch_event
from vibe3.services.check_service import CheckService
from vibe3.services.flow_service import FlowService
from vibe3.services.label_utils import (
    clean_old_state_labels,
    should_skip_from_queue,
)

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.roles.definitions import TriggerableRoleDefinition

# Hard limit to prevent extreme tick duration in edge cases
MAX_INTENTS_PER_TICK = 10


class GlobalDispatchCoordinator:
    """Frozen queue with state-change requeue semantics."""

    def __init__(
        self,
        config: OrchestraConfig,
        capacity: CapacityService,
        github: GitHubClient,
        store: "SQLiteClient",
        flow_manager: FlowManagerPort,
        registry: "SessionRegistryService | None" = None,
        executor: ThreadPoolExecutor | None = None,
        queue_persistence: QueuePersistencePort | None = None,
    ) -> None:
        self._config = config
        self._capacity = capacity
        self._github = github
        self._store = store
        self._flow_manager: FlowManagerPort = flow_manager
        self._registry = registry
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows
        )
        self._owns_executor = executor is None
        self._frozen_queue: list[QueueEntry] | None = None
        self._qualify_gate = QualifyGateService(config, github, store, flow_manager)
        self._check_service: CheckService | None = None
        self._dispatch_paused = False
        self._supervisor_label = config.supervisor_handoff.issue_label

        # Initialize queue persistence service
        # Allow injection for testability; default to concrete implementation
        if queue_persistence is None:
            # Import concrete implementation only when needed
            from vibe3.orchestra.queue_persistence_service import (
                QueuePersistenceService,
            )

            self._queue_persistence: QueuePersistencePort = QueuePersistenceService(
                store=store,
                config=config,
                github=github,
                registry=registry,
                supervisor_label=self._supervisor_label,
                load_issue=self._load_issue,
            )
        else:
            self._queue_persistence = queue_persistence

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

    async def _poll_issues_by_state(self, state: IssueState) -> list[IssueInfo]:
        """Poll GitHub for issues with a specific state label."""
        raw_issues = await asyncio.get_running_loop().run_in_executor(
            self._executor,
            lambda: self._github.list_issues(
                limit=100,
                state="open",
                assignee=None,
                repo=self._config.repo,
                label=state.to_label(),
            ),
        )

        # BLOCKED bypass: skip qualify gate so falsely-unblocked issues
        # enter the queue.  Qualification is deferred to
        # qualify_blocked_issue() at dispatch time (coordinate()).
        if state == IssueState.BLOCKED:
            raw_selected = collect_raw_issues_without_qualify(raw_issues)

            # Apply skip filter after collection (preserves original behavior
            # where issues flow through qualify gate for side effects)
            selected: list[IssueInfo] = []
            for issue in raw_selected:
                if should_skip_from_queue(
                    issue,
                    supervisor_label=self._supervisor_label,
                    manager_usernames=self._config.get_manager_usernames(),
                    require_manager_assignee=True,
                ):
                    continue
                selected.append(issue)

            append_orchestra_event(
                "dispatcher",
                f"poll_issues_by_state({state.value}): "
                f"{len(selected)} ready issues (bypassed qualify gate)",
            )
            return selected

        ready = select_ready_issues(
            raw_issues,
            state,
            self._config,
            self._github,
            self._store,
            self._flow_manager,
            self._qualify_gate,
            self._supervisor_label,
        )

        append_orchestra_event(
            "dispatcher",
            f"poll_issues_by_state({state.value}): {len(ready)} ready issues",
        )
        return ready

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
        publish(build_label_dispatch_event(role, issue, branch=branch, tick_id=tick_id))

    def _flow_context(self, issue_number: int) -> tuple[str, dict[str, object] | None]:
        """Get flow context for an issue (backward compatibility)."""
        return get_flow_context(
            issue_number, self._config, self._github, self._store, self._flow_manager
        )

    def _load_issue(self, issue_number: int) -> IssueInfo | None:
        """Load issue snapshot (backward compatibility)."""
        return load_issue(issue_number, self._config, self._github)

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

    def _health_check_before_dispatch(self, issue: IssueInfo) -> bool:
        """Check structural health before dispatch.

        SCOPE: Structural validity only. This method does NOT make blocked
        semantic decisions — those belong in qualify-gate. It only validates:
        - Issue closed / PR merged (terminal)
        - Missing worktree / invalid refs
        - Transient fail-open (network/auth errors, missing flow records)
        - Terminal flow states (done/aborted/stale)

        Blocked/unblocked truth reconciliation is handled by qualify-gate,
        not by health check. There is no second unblock path here.

        Returns:
            True if issue can be dispatched (healthy or transient error)
            False if issue should be skipped (genuine failure or terminal state)
        """
        # Get the canonical branch for this issue
        branch, _ = self._flow_context(issue.number)

        # If no branch exists, fail open only for manager entry states that
        # can create a fresh task scene. Worker states require an existing flow
        # context; otherwise role builders fall back to a canonical branch that
        # may not exist, causing invalid worktree dispatch.
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

        # Use CheckService for unified health check
        if self._check_service is None:
            self._check_service = CheckService(
                store=self._store,
                git_client=self._flow_manager.git,
                github_client=self._github,
            )
        result = self._check_service.verify_branch(branch)

        # Get flow status to determine if dispatch should proceed
        flow_state = self._store.get_flow_state(branch)
        flow_status = (
            flow_state.get("flow_status", "active") if flow_state else "active"
        )

        # Determine dispatch eligibility:
        # - Fail-open for transient errors (network/auth) and missing flow records
        # - Return False for genuine consistency failures (issue closed, PR merged)
        # - Return False if flow is done/aborted (terminal state)
        # - Return True if flow is healthy and active
        if not result.is_valid:
            # Check if this is a transient/expected error that should fail-open
            transient_errors = [
                "Cannot verify",  # Network/auth errors
                "No flow record",  # Missing flow_state (new issues)
            ]
            is_transient = any(
                any(err.startswith(prefix) for err in result.issues)
                for prefix in transient_errors
            )

            if is_transient:
                # Fail-open: allow dispatch despite transient errors
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: fail-open for #{issue.number} "
                    f"(transient error: {', '.join(result.issues)})",
                )
                return True

            # Genuine consistency failure - block and skip dispatch
            reason = f"Health check failed: {', '.join(result.issues)}"
            block_succeeded = False
            try:
                FlowService(
                    store=self._store, git_client=self._flow_manager.git
                ).block_flow(branch=branch, reason=reason, actor="orchestra:dispatcher")
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

        if flow_status in ("done", "aborted", "stale"):
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: skipped #{issue.number} "
                f"(flow is {flow_status})",
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

    async def _probe_for_non_blocked_candidates(self) -> bool:
        """Check if any non-blocked state issue is available after a paused period."""
        for state in (
            IssueState.REVIEW,
            IssueState.MERGE_READY,
            IssueState.IN_PROGRESS,
            IssueState.CLAIMED,
            IssueState.HANDOFF,
            IssueState.READY,
        ):
            try:
                issues = await self._poll_issues_by_state(state)
            except Exception as exc:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: probe failed for {state.value}: {exc}",
                )
                continue
            if issues:
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

            if should_skip_from_queue(
                issue,
                supervisor_label=self._supervisor_label,
                manager_usernames=self._config.get_manager_usernames(),
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

            # === NEW: Pre-dispatch health check ===
            if not self._health_check_before_dispatch(issue):
                self._frozen_queue.pop(index)
                continue
            # === END health check ===

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
            # load_issue is set on construction for Protocol instances
            # Only reassign for concrete QueuePersistenceService
            if hasattr(self._queue_persistence, "load_issue"):
                self._queue_persistence.load_issue = self._load_issue  # type: ignore[attr-defined]
            restored = self._queue_persistence.restore()
            self._frozen_queue = restored if restored is not None else []
            self._queue_persistence.frozen_queue = self._frozen_queue
            self._check_service = None  # Invalidate cache on restore

        # Step 2: Promote progressed entries (state changes)
        self._queue_persistence.frozen_queue = self._frozen_queue
        # load_issue is set on construction for Protocol instances
        # Only reassign for concrete QueuePersistenceService
        if hasattr(self._queue_persistence, "load_issue"):
            self._queue_persistence.load_issue = self._load_issue  # type: ignore[attr-defined]
        cleared_all = self._queue_persistence.promote()
        if cleared_all:
            self._check_service = None  # Invalidate when queue is cleared
        self._frozen_queue = self._queue_persistence.frozen_queue

        # Normalize after promotion: promote() may set
        # frozen_queue = None when all entries are removed
        if self._frozen_queue is None:
            self._frozen_queue = []

        paused_with_pending_blocked = False

        # Step 3: Paused mode waits for human task resume to create a
        # non-blocked candidate again. Keep existing waiting entries resident.
        # Blocked-only rebuilds get one dispatch-time qualify pass before the
        # coordinator enters a quiet paused state.
        if self._dispatch_paused:
            if self._has_actionable_entries():
                self._dispatch_paused = False
            elif self._has_pending_blocked_entries():
                paused_with_pending_blocked = True
            else:
                has_non_blocked = await self._probe_for_non_blocked_candidates()
                if not has_non_blocked:
                    append_orchestra_event(
                        "dispatcher",
                        "GlobalDispatchCoordinator: dispatch paused "
                        "(all collected candidates remain blocked)",
                    )
                    self._queue_persistence.frozen_queue = self._frozen_queue
                    self._queue_persistence.persist()
                    return
                self._dispatch_paused = False

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

        # Step 6: Rebuild active candidates once active queue is exhausted.
        need_collect = self._should_collect_after_dispatch(dispatched_count)
        if need_collect:
            fresh = await self._collect_frozen_queue()
            self._check_service = None  # Invalidate cache
            if fresh and all(entry.collected_state == "blocked" for entry in fresh):
                self._dispatch_paused = True
                if paused_with_pending_blocked:
                    append_orchestra_event(
                        "dispatcher",
                        "GlobalDispatchCoordinator: dispatch paused "
                        "(blocked candidates unchanged after qualify)",
                    )
                else:
                    self._frozen_queue = self._merge_queue(
                        self._frozen_queue or [], fresh
                    )
                append_orchestra_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: dispatch paused "
                    "(rebuild found only blocked issues)",
                )
            else:
                self._dispatch_paused = False
                self._frozen_queue = self._merge_queue(self._frozen_queue or [], fresh)
