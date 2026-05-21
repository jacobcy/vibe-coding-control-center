"""Stateless scan-dispatch coordinator.

Queue rule:
1. Each tick: fresh scan from GitHub for dispatchable states
2. Get active issues from tmux sessions + SessionRegistry
3. Filter out active, DONE, supervisor-labeled, assignee-missing issues
4. Sort by queue ordering rules
5. Dispatch up to available capacity
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
from vibe3.orchestra.queue_ordering import sort_ready_issues
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


class GlobalDispatchCoordinator:
    """Stateless scan-dispatch coordinator (no frozen queue)."""

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
        self._qualify_gate = QualifyGateService(config, github, store, flow_manager)
        self._check_service: CheckService | None = None
        self._supervisor_label = config.supervisor_handoff.issue_label

    def shutdown(self) -> None:
        """Shutdown the executor if we own it."""
        if self._owns_executor and self._executor:
            self._executor.shutdown(wait=True)

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

    def _get_active_issue_numbers(self) -> set[int]:
        """Get set of issue numbers currently in active sessions."""
        active_issues: set[int] = set()

        # Check SessionRegistry for active sessions
        if self._registry is not None:
            sessions = self._store.list_live_runtime_sessions()
            for session in sessions:
                target_id = session.get("target_id")
                if target_id and str(target_id).startswith("issue-"):
                    try:
                        issue_number = int(str(target_id).split("-", 1)[1])
                        active_issues.add(issue_number)
                    except (ValueError, IndexError):
                        pass

        return active_issues

    async def _scan_dispatchable_states(self) -> list[IssueInfo]:
        """Scan GitHub for issues in dispatchable states.

        Returns:
            List of IssueInfo objects from dispatchable states
        """
        candidates: list[IssueInfo] = []
        seen_issue_numbers: set[int] = set()

        append_orchestra_event(
            "dispatcher",
            "GlobalDispatchCoordinator: starting state scan",
        )

        # Collect issues from all dispatchable states
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
                # Poll GitHub for issues with this state label
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

                # Process raw issues
                for item in raw_issues:
                    labels = normalize_labels(item.get("labels"))
                    if not any(lbl.startswith("state/") for lbl in labels):
                        continue

                    issue = IssueInfo.from_github_payload(item)
                    if issue is None:
                        continue

                    # Skip duplicates
                    if issue.number in seen_issue_numbers:
                        continue
                    seen_issue_numbers.add(issue.number)

                    # For BLOCKED issues: skip qualify gate at scan time
                    # Qualification is deferred to dispatch time (see coordinate())
                    if state == IssueState.BLOCKED:
                        if should_skip_from_queue(
                            issue,
                            supervisor_label=self._supervisor_label,
                            manager_usernames=self._config.get_manager_usernames(),
                            require_manager_assignee=True,
                        ):
                            continue
                        candidates.append(issue)
                        continue

                    # For other states: check qualify gate immediately
                    # (preserve existing behavior from select_ready_issues)
                    branch, flow_state = get_flow_context(
                        issue.number,
                        self._config,
                        self._github,
                        self._store,
                        self._flow_manager,
                    )

                    target = self._qualify_gate.run_qualify_gate(
                        issue, branch, flow_state, issue.labels, state
                    )
                    if target is None or target != state:
                        continue

                    if should_skip_from_queue(
                        issue,
                        supervisor_label=self._supervisor_label,
                        manager_usernames=self._config.get_manager_usernames(),
                        require_manager_assignee=True,
                    ):
                        continue

                    candidates.append(issue)

            except Exception as exc:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: scan failed for {state.value}: {exc}",
                )
                logger.bind(
                    domain="global_dispatch",
                    state=state.value,
                ).error(f"scan failed for {state.value}: {exc}")

        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: scan complete, {len(candidates)} candidates",
        )

        return candidates

    def get_queued_issue_numbers(self) -> set[int]:
        """Get set of issue numbers currently in flight.

        Returns issues with active sessions (tmux + registry).
        """
        return self._get_active_issue_numbers()

    async def coordinate(self, tick_id: int = 0) -> None:
        """Run one heartbeat tick: scan, filter, sort, dispatch.

        Args:
            tick_id: Current tick number from heartbeat (default: 0)
        """
        # 1. Who is running?
        active_issues = self._get_active_issue_numbers()

        # 2. What is dispatchable? (fresh scan from GitHub)
        candidates = await self._scan_dispatchable_states()

        # 3. Filter: remove active, DONE
        candidates = [c for c in candidates if c.number not in active_issues]
        candidates = [c for c in candidates if c.state != IssueState.DONE]

        if not candidates:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: no candidates after filtering",
            )
            return

        # 4. Sort by queue ordering rules
        candidates = sort_ready_issues(candidates)

        # 5. Check capacity
        status = self._capacity.get_capacity_status("manager")
        available_slots = status["remaining"]

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: capacity full",
            )
            return

        # 6. Dispatch up to available slots
        dispatched_count = 0
        for issue in candidates[:available_slots]:
            # For BLOCKED issues: run qualify gate at dispatch time
            if issue.state == IssueState.BLOCKED:
                target_state = self._qualify_gate.qualify_blocked_issue(issue)

                # Check degraded mode
                degraded = get_degraded_manager()
                if degraded.is_degraded():
                    degraded_reason = degraded.get_reason()
                    reason_value = degraded_reason.value if degraded_reason else None
                    logger.bind(
                        domain="orchestra",
                        action="dispatch_blocked",
                        degraded_mode=True,
                        reason=reason_value,
                        issue_number=issue.number,
                    ).warning(f"Qualification of #{issue.number} entered degraded mode")

                if target_state is None:
                    continue

                role = find_role_for_state(target_state)
                if role is None:
                    continue
            elif issue.state is not None:
                role = find_role_for_state(issue.state)
                if role is None:
                    continue
            else:
                continue

            # Pre-dispatch health check
            if not self._health_check_before_dispatch(issue):
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: skipped #{issue.number} "
                    "(health check failed)",
                )
                continue

            # Emit dispatch intent
            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatch-intent{reset} "
                f"#{issue.number} ({role.registry_role})",
            )
            self._emit_dispatch_intent(role, issue, tick_id)
            dispatched_count += 1

            logger.bind(
                domain="global_dispatch",
                role=role.registry_role,
                issue=issue.number,
            ).info(
                f"Emitted dispatch intent for #{issue.number} "
                f"({role.registry_role})"
            )

        if dispatched_count > 0:
            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatch-intent="
                f"{dispatched_count}{reset}",
            )
