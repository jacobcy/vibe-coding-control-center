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
from vibe3.domain import publish
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.pr import PRState
from vibe3.orchestra.flow_dispatch import FlowManager
from vibe3.orchestra.issue_loader import (
    find_role_for_state,
    get_flow_context,
    load_issue,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_operations import (
    promote_progressed_entries,
    select_ready_issues,
)
from vibe3.roles.registry import build_label_dispatch_event
from vibe3.utils.label_utils import clean_old_state_labels, should_skip_from_queue

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
        self._supervisor_label = config.supervisor_handoff.issue_label

        # Load persisted queue on init (restart recovery)
        self._frozen_queue = self._restore_queue()

    def shutdown(self) -> None:
        """Shutdown the executor if we own it."""
        if self._owns_executor and self._executor:
            self._executor.shutdown(wait=True)

    def _restore_queue(self) -> list[QueueEntry] | None:
        """Load persisted queue from database, removing invalid entries."""
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
        removed_count = 0

        for entry in entries:
            issue_number = entry["issue_number"]
            issue = self._load_issue(issue_number)

            skip = (
                issue is None
                or issue.state == IssueState.DONE
                or should_skip_from_queue(
                    issue,
                    supervisor_label=self._supervisor_label,
                    manager_usernames=self._config.manager_usernames,
                    require_manager_assignee=True,
                )
            )
            if skip:
                self._store.remove_from_frozen_queue(issue_number)
                removed_count += 1
            else:
                restored.append(
                    QueueEntry(
                        issue_number=issue_number,
                        collected_state=entry.get("collected_state"),
                        waiting_state=None,
                    )
                )

        logger.bind(domain="global_dispatch").info(
            f"Restored {len(restored)}, removed {removed_count}"
        )
        return restored if restored else None

    def _persist_queue(self) -> None:
        """Persist current frozen queue to database."""
        if not self._frozen_queue:
            self._store.clear_frozen_queue()
            return
        self._store.save_frozen_queue(
            [
                {
                    "issue_number": e.issue_number,
                    "collected_state": e.collected_state,
                    "waiting_state": e.waiting_state,
                }
                for e in self._frozen_queue
            ]
        )

    def get_queued_issue_numbers(self) -> set[int]:
        """Get issue numbers currently in the frozen queue."""
        if self._frozen_queue:
            return {e.issue_number for e in self._frozen_queue}
        return set()

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
        """Emit dispatch intent for an issue."""
        clean_old_state_labels(issue, role, self._config)
        branch, _ = self._flow_context(issue.number)
        publish(build_label_dispatch_event(role, issue, branch=branch, tick_id=tick_id))

    def _flow_context(self, issue_number: int) -> tuple[str, dict[str, object] | None]:
        """Get flow context for an issue."""
        return get_flow_context(
            issue_number, self._config, self._github, self._store, self._flow_manager
        )

    def _load_issue(self, issue_number: int) -> IssueInfo | None:
        """Load issue snapshot."""
        return load_issue(issue_number, self._config, self._github)

    def _health_check_before_dispatch(self, issue: IssueInfo) -> bool:
        """Check issue health before dispatch.
        Returns False if issue should be skipped."""
        # Check: Issue closed on GitHub
        try:
            payload = self._github.view_issue(issue.number, repo=self._config.repo)
        except Exception as e:
            logger.bind(domain="orchestra").error(
                f"Health check failed for #{issue.number}: {e}"
            )
            return True
        if isinstance(payload, dict) and payload.get("state") == "CLOSED":
            append_orchestra_event(
                "dispatcher",
                f"Skipped #{issue.number} (issue is closed on GitHub)",
            )
            return False

        # Check: PR merged (auto-close issue)
        pr_number = self._flow_manager.get_pr_for_issue(issue.number)
        if pr_number:
            try:
                pr = self._github.get_pr(pr_number=int(pr_number))
            except Exception as e:
                logger.bind(domain="orchestra").warning(
                    f"Failed to check PR #{pr_number} for issue #{issue.number}: {e}"
                )
                return True
            if pr is not None and pr.state == PRState.MERGED:
                try:
                    self._github.close_issue_if_open(
                        issue.number,
                        closing_comment=(
                            f"PR #{pr_number} 已合并，系统自动关闭此 issue。"
                        ),
                        repo=self._config.repo,
                    )
                except Exception as e:
                    logger.bind(domain="orchestra").error(
                        f"Failed to close issue #{issue.number} after PR merge: {e}"
                    )
                append_orchestra_event(
                    "dispatcher",
                    f"Skipped #{issue.number} "
                    f"(PR #{pr_number} merged, issue auto-closed)",
                )
                return False
        return True

    async def coordinate(self, tick_id: int = 0) -> None:
        """Run one heartbeat tick against the frozen queue."""
        if self._frozen_queue is None or len(self._frozen_queue) == 0:
            self._frozen_queue = await self._collect_frozen_queue()
            if not self._frozen_queue:
                append_orchestra_event(
                    "dispatcher", "GlobalDispatchCoordinator: no candidates"
                )
                self._persist_queue()
                return

        self._promote_progressed_entries()

        if not self._frozen_queue:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: queue emptied by state changes",
            )
            self._persist_queue()
            return

        status = self._capacity.get_capacity_status("manager")
        available_slots = status["remaining"]

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher", "GlobalDispatchCoordinator: capacity full"
            )
            return

        dispatched_count = 0
        index = 0
        while index < len(self._frozen_queue):
            if dispatched_count >= available_slots:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
                    "skipped remaining (capacity full)",
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

            entry.collected_state = issue.state.value

            if entry.waiting_state is not None:
                index += 1
                continue

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

            if issue.state == IssueState.BLOCKED:
                target_state = self._qualify_gate.qualify_blocked_issue(issue)
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

            if not self._health_check_before_dispatch(issue):
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: skipped #{issue.number} "
                    "(health check failed)",
                )
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

        self._persist_queue()

    async def _collect_frozen_queue(self) -> list[QueueEntry]:
        """Collect a new frozen queue only when the current one is empty."""
        queue: list[QueueEntry] = []
        seen_issue_numbers: set[int] = set()
        append_orchestra_event(
            "dispatcher", "GlobalDispatchCoordinator: starting queue collection"
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
                    f"GlobalDispatchCoordinator: collect_ready_issues failed "
                    f"for {state.value}: {exc}",
                )
                logger.bind(domain="global_dispatch", state=state.value).error(
                    f"poll_issues_by_state failed for {state.value}: {exc}"
                )
        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: queue collection complete, "
            f"total={len(queue)} issues",
        )
        self._persist_queue()
        return queue

    def _promote_progressed_entries(self) -> None:
        """Move progressed issues to the front; remove blocked/failed from queue."""
        if not self._frozen_queue:
            return

        queue_dicts = [
            {
                "issue_number": e.issue_number,
                "collected_state": e.collected_state,
                "waiting_state": e.waiting_state,
            }
            for e in self._frozen_queue
        ]

        promoted, retained, removed = promote_progressed_entries(
            queue_dicts,
            self._config,
            self._github,
            self._registry,
            self._supervisor_label,
            load_issue_func=self._load_issue,
        )

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

        self._frozen_queue = (
            promoted_entries + retained_entries
            if (promoted_entries or retained_entries)
            else None
        )
        self._persist_queue()
