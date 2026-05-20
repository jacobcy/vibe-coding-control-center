"""Frozen-queue dispatch coordinator.

Queue rule:
1. Only collect a new queue when the frozen queue is empty
2. Keep queued issues resident across ticks
3. After dispatch, an issue waits for its state label to change
4. Once state changes, move that issue to the front of the queue
5. Only capacity uses tmux session counting
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
from vibe3.orchestra.flow_dispatch import FlowManager
from vibe3.orchestra.issue_loader import (
    find_role_for_state,
    get_flow_context,
    load_issue,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_operations import select_ready_issues
from vibe3.orchestra.queue_persistence_mixin import (
    QueueEntry,
    QueuePersistenceMixin,
)
from vibe3.roles.registry import build_label_dispatch_event
from vibe3.services.check_service import CheckService
from vibe3.services.flow_service import FlowService
from vibe3.utils.label_utils import (
    clean_old_state_labels,
    normalize_labels,
    should_skip_from_queue,
)

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.roles.definitions import TriggerableRoleDefinition


class GlobalDispatchCoordinator(QueuePersistenceMixin):
    """Frozen queue with state-change requeue semantics."""

    def __init__(
        self,
        config: OrchestraConfig,
        capacity: CapacityService,
        github: GitHubClient,
        store: "SQLiteClient",
        flow_manager: FlowManager,
        registry: "SessionRegistryService | None" = None,
        executor: ThreadPoolExecutor | None = None,
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
        self._check_service: CheckService | None = None
        self._supervisor_label = config.supervisor_handoff.issue_label

        # Load persisted queue on init (restart recovery)
        self._frozen_queue = self._restore_queue()

    def shutdown(self) -> None:
        """Shutdown the executor if we own it."""
        if self._owns_executor and self._executor:
            self._executor.shutdown(wait=True)

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
            selected: list[IssueInfo] = []
            for item in raw_issues:
                labels = normalize_labels(item.get("labels"))
                if not any(lbl.startswith("state/") for lbl in labels):
                    continue
                issue = IssueInfo.from_github_payload(item)
                if issue is None:
                    continue
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

        # If no branch exists, fail open (allow dispatch for new issues)
        if not branch:
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

    async def coordinate(self, tick_id: int = 0) -> None:
        """Run one heartbeat tick against the frozen queue.

        Args:
            tick_id: Current tick number from heartbeat (default: 0)
        """
        if self._frozen_queue is None or len(self._frozen_queue) == 0:
            self._frozen_queue = await self._collect_frozen_queue()
            self._check_service = None  # Invalidate cache when queue is rebuilt
            # Persist freshly collected queue after assignment
            self._persist_queue()
            if not self._frozen_queue:
                append_orchestra_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: no candidates",
                )
                return

        self._promote_progressed_entries()

        if not self._frozen_queue:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: queue emptied by state changes",
            )
            return

        status = self._capacity.get_capacity_status("manager")
        available_slots = status["remaining"]

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: capacity full",
            )
            return

        dispatched_count = 0
        index = 0
        while index < len(self._frozen_queue):
            if dispatched_count >= available_slots:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
                    f"skipped remaining (capacity full)",
                )
                return

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

            # For BLOCKED issues: run qualify gate at intent time
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
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: skipped #{issue.number} "
                    "(health check failed)",
                )
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

        # Persist queue state after dispatch mutations
        self._persist_queue()
