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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_labels import GhIssueLabelPort
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.execution.capacity_service import CapacityService
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_ordering import sort_ready_issues
from vibe3.roles.registry import LABEL_DISPATCH_ROLES
from vibe3.utils.label_utils import should_skip_from_queue

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.roles.definitions import TriggerableRoleDefinition


@dataclass
class QueueEntry:
    """Frozen queue entry tracked only by issue identity and wait state."""

    issue_number: int
    collected_state: str | None = None
    waiting_state: str | None = None


class GlobalDispatchCoordinator:
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
        # Get supervisor_label from config
        self._supervisor_label = config.supervisor_handoff.issue_label

    def shutdown(self) -> None:
        """Shutdown the executor if we own it."""
        if self._owns_executor and self._executor:
            self._executor.shutdown(wait=True)

    def _find_role_for_state(
        self, state: IssueState
    ) -> TriggerableRoleDefinition | None:
        """Find the role definition for a state label."""
        for role in LABEL_DISPATCH_ROLES:
            if role.trigger_state == state:
                return role
        return None

    async def _poll_issues_by_state(self, state: IssueState) -> list[IssueInfo]:
        """Poll GitHub for issues with a specific state label.

        Args:
            state: Issue state to poll for

        Returns:
            List of ready issues for this state
        """
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

        ready = self._select_ready_issues(raw_issues, state)

        append_orchestra_event(
            "dispatcher",
            f"poll_issues_by_state({state.value}): {len(ready)} ready issues",
        )
        return ready

    def _emit_dispatch_intent(
        self, role: "TriggerableRoleDefinition", issue: IssueInfo
    ) -> None:
        """Emit dispatch intent for an issue.

        Args:
            role: Role definition for this dispatch
            issue: Issue to dispatch
        """
        from vibe3.domain import publish
        from vibe3.roles.registry import build_label_dispatch_event

        # Pre-dispatch cleanup: remove conflicting state/* labels
        # This ensures a single state label before dispatch.
        old_state_labels = [
            lb
            for lb in issue.labels
            if lb.startswith("state/") and lb != role.trigger_state.to_label()
        ]
        if old_state_labels:
            try:
                label_port = GhIssueLabelPort(repo=self._config.repo)
                for old_lb in old_state_labels:
                    label_port.remove_issue_label(issue.number, old_lb)
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"Failed to clean old state labels for #{issue.number}: {exc}"
                )

        branch, _ = self._flow_context(issue.number)
        publish(build_label_dispatch_event(role, issue, branch=branch))

    def _flow_context(self, issue_number: int) -> tuple[str, dict[str, object] | None]:
        """Get flow context (branch and state) for an issue.

        Args:
            issue_number: Issue number to look up

        Returns:
            Tuple of (branch, flow_state)
        """
        flow = self._flow_manager.get_flow_for_issue(issue_number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        if not branch:
            return "", None
        return branch, self._store.get_flow_state(branch)

    def _select_ready_issues(
        self, raw_issues: list[dict[str, object]], trigger_state: IssueState
    ) -> list[IssueInfo]:
        """Select ready issues by filtering through qualify gate and other checks.

        Args:
            raw_issues: Raw issue payloads from GitHub
            trigger_state: The trigger state being collected

        Returns:
            Filtered and sorted ready issues
        """
        selected: list[IssueInfo] = []
        role = self._find_role_for_state(trigger_state)
        if role is None:
            return selected

        for item in raw_issues:
            labels = self._normalize_labels(item.get("labels"))

            # Untracked state: ignore issues with no state labels
            if not any(lbl.startswith("state/") for lbl in labels):
                continue

            # Skip blocked issues (FAILED unified to BLOCKED)
            if IssueState.BLOCKED.to_label() in labels:
                continue

            issue = IssueInfo.from_github_payload(item)
            if issue is None:
                continue

            # BLOCKED_ROLE: collect all candidates without qualify gate.
            # Gate runs at intent time in GlobalDispatchCoordinator.
            if role.trigger_name == "blocked":
                selected.append(issue)
                continue

            branch, flow_state = self._flow_context(issue.number)

            # Qualify Gate — returns target state or None if blocked
            target = self._qualify_gate.run_qualify_gate(
                issue, branch, flow_state, labels, trigger_state
            )
            if target is None or target != trigger_state:
                continue

            # Role-specific branch existence requirements
            if role.trigger_name != "manager":
                if not branch or not self._is_auto_task_branch(branch):
                    continue
                if not self._flow_manager.git.branch_exists(branch):
                    append_orchestra_event(
                        "dispatcher",
                        f"skip #{issue.number}: branch '{branch}' not found in git",
                    )
                    continue

            # Verify assignee/supervisor filters
            # Always require manager assignee for all dispatch stages
            if should_skip_from_queue(
                issue,
                supervisor_label=self._supervisor_label,
                manager_usernames=self._config.manager_usernames,
                require_manager_assignee=True,
            ):
                continue

            selected.append(issue)

        return sort_ready_issues(selected)

    @staticmethod
    def _normalize_labels(raw_labels: object) -> list[str]:
        """Normalize raw labels from GitHub API.

        Args:
            raw_labels: Raw labels object from GitHub

        Returns:
            List of label names
        """
        labels: list[str] = []
        if not isinstance(raw_labels, list):
            return labels
        for item in raw_labels:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    labels.append(name)
        return labels

    @staticmethod
    def _is_auto_task_branch(branch: str) -> bool:
        """Check if branch is an auto-task branch.

        Args:
            branch: Branch name to check

        Returns:
            True if branch starts with 'task/issue-'
        """
        return branch.startswith("task/issue-")

    async def coordinate(self) -> None:
        """Run one heartbeat tick against the frozen queue."""
        if self._frozen_queue is None or len(self._frozen_queue) == 0:
            self._frozen_queue = await self._collect_frozen_queue()
            if not self._frozen_queue:
                append_orchestra_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: no candidates",
                )
                return

        self._promote_progressed_entries()

        # Check if queue was emptied by _promote_progressed_entries
        # (e.g., all issues became blocked/done)
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
                manager_usernames=self._config.manager_usernames,
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

            # Update collected_state to current state for tracking
            # No longer "avoid" state changes - assignee check is sufficient
            entry.collected_state = issue.state.value

            if entry.waiting_state is not None:
                index += 1
                continue

            # Per-issue active session gate:
            # Prevent dispatch if ANY worker role session is still live for this issue.
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

            # For BLOCKED issues: run qualify gate at intent time (lazy evaluation)
            if issue.state == IssueState.BLOCKED:
                target_state = self._qualify_gate.qualify_blocked_issue(issue)
                if target_state is None:
                    # Still blocked — remove from frozen queue, re-collected next tick
                    self._frozen_queue.pop(index)
                    continue
                role = self._find_role_for_state(target_state)
                if role is None:
                    self._frozen_queue.pop(index)
                    continue
                entry.collected_state = target_state.value
            else:
                role = self._find_role_for_state(issue.state)
                if role is None:
                    self._frozen_queue.pop(index)
                    continue

            try:
                green = "\033[32m"
                reset = "\033[0m"
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: {green}dispatch-intent{reset} "
                    f"#{issue.number} ({role.registry_role})",
                )
                self._emit_dispatch_intent(role, issue)
                # For BLOCKED issues, waiting_state must track the TARGET state
                # (qualify gate already changed GitHub labels to target_state).
                # Using issue.state.value ("blocked") cause _promote_progressed_entries
                # to detect a false state change and re-dispatch on the next tick.
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
            except Exception as exc:
                logger.bind(
                    domain="global_dispatch",
                    role=role.registry_role,
                    issue=issue.number,
                ).error(f"Dispatch failed for #{issue.number}: {exc}")
            index += 1

        if dispatched_count > 0:
            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatch-intent="
                f"{dispatched_count}{reset}",
            )

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
            IssueState.BLOCKED,  # Qualify gate runs at intent time
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

    def _promote_progressed_entries(self) -> None:
        """Move progressed issues to the front; remove blocked/failed from queue.

        Blocked and failed states require human intervention and should not be
        automatically retried by the dispatcher. Remove them from the frozen queue
        to avoid wasting dispatch slots.
        """
        if not self._frozen_queue:
            return

        promoted: list[QueueEntry] = []
        retained: list[QueueEntry] = []
        removed: list[QueueEntry] = []
        for entry in self._frozen_queue:
            if entry.waiting_state is None:
                retained.append(entry)
                continue

            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
                continue

            if should_skip_from_queue(
                issue,
                supervisor_label=self._supervisor_label,
                manager_usernames=self._config.manager_usernames,
                require_manager_assignee=True,
            ):
                removed.append(entry)
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                    "from queue (supervisor or assignee check failed)",
                )
                continue

            current_state = issue.state.value
            if current_state == entry.waiting_state:
                # State unchanged. Check whether the agent session that would
                # advance it is still alive.  If no session exists the label can
                # never change ─ promote the entry for re-dispatch so the queue
                # can eventually drain and re-collect.
                if self._registry is not None:
                    active = self._registry.get_live_sessions_for_issue(
                        issue_number=entry.issue_number,
                        roles=["manager", "planner", "executor", "reviewer"],
                    )
                    if not active:
                        entry.waiting_state = None
                        promoted.append(entry)
                        append_orchestra_event(
                            "dispatcher",
                            f"GlobalDispatchCoordinator: requeued "
                            f"#{entry.issue_number} "
                            f"(no active session, state={current_state})",
                        )
                        continue
                retained.append(entry)
                continue

            # Blocked state requires human intervention - remove from queue
            if current_state == "blocked":
                removed.append(entry)
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                    f"from queue (state changed to {current_state}, "
                    f"requires human intervention)",
                )
                continue

            # Progress detected (state changed to non-terminal) - promote to front
            entry.waiting_state = None
            entry.collected_state = current_state  # Sync with current state
            promoted.append(entry)
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: requeued #{entry.issue_number} "
                f"to front after state change to {current_state}",
            )

        # Update frozen queue: promoted + retained (removed entries discarded)
        if promoted or retained:
            self._frozen_queue = promoted + retained
        else:
            # All entries removed (e.g., all issues became blocked)
            # Clear frozen queue to trigger fresh collection on next tick
            self._frozen_queue = None

    def _load_issue(self, issue_number: int) -> IssueInfo | None:
        """Load the current issue snapshot for an already-frozen issue."""
        try:
            payload = self._github.view_issue(issue_number, repo=self._config.repo)
        except Exception as exc:
            logger.bind(domain="global_dispatch", issue=issue_number).error(
                f"view_issue failed for #{issue_number}: {exc}"
            )
            return None
        if not isinstance(payload, dict):
            return None
        return IssueInfo.from_github_payload(payload)
