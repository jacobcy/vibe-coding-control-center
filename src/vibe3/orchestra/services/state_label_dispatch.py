"""State-driven trigger service for manager/plan/run/review intent emission."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import (
    IssueInfo,
    IssueState,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_ordering import sort_ready_issues
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.runtime.service_protocol import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.capacity_service import CapacityService


def _normalize_labels(raw_labels: object) -> list[str]:
    labels: list[str] = []
    if not isinstance(raw_labels, list):
        return labels
    for item in raw_labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                labels.append(name)
    return labels


def _is_auto_task_branch(branch: str) -> bool:
    return branch.startswith("task/issue-")


class StateLabelDispatchService(ServiceBase):
    """Dispatch manager or downstream agents from issue state labels.

    The per-role dispatch logic (status_field, dispatch_predicate) is owned by
    TriggerableRoleDefinition. This service is a thin runtime loop that polls
    GitHub, filters using role-declared predicates, and publishes domain events.
    """

    event_types: list[str] = []

    @property
    def service_name(self) -> str:
        return (
            f"{type(self).__name__}("
            f"{self.role_def.trigger_name}:{self.role_def.trigger_state.value})"
        )

    def __init__(
        self,
        config: OrchestraConfig,
        *,
        github: GitHubClient | None = None,
        executor: ThreadPoolExecutor | None = None,
        flow_manager: FlowManager | None = None,
        registry: "SessionRegistryService | None" = None,
        capacity: "CapacityService | None" = None,
        role_def: TriggerableRoleDefinition,
    ) -> None:
        self.config = config
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._github = github or GitHubClient()
        self._flow_manager = flow_manager or FlowManager(config, registry=registry)
        self._store = SQLiteClient()
        self._registry = registry
        self._capacity = capacity
        self._dispatch_guard = asyncio.Lock()
        self.role_def = role_def

    # trigger_name / trigger_state kept as properties for callers that access them.
    @property
    def trigger_name(self) -> str:
        return self.role_def.trigger_name

    @property
    def trigger_state(self) -> IssueState:
        return self.role_def.trigger_state

    async def handle_event(self, event: GitHubEvent) -> None:
        return

    async def collect_ready_issues(self) -> list[IssueInfo]:
        """Scan and return ready issues without dispatching.

        This method is for GlobalDispatchCoordinator to collect issues for
        capacity-aware dispatch. Capacity checking is done by coordinator.

        Returns:
            Filtered and sorted ready issues list
        """
        async with self._dispatch_guard:
            raw_issues = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self._github.list_issues(
                    limit=100,
                    state="open",
                    assignee=None,
                    repo=self.config.repo,
                    label=self.role_def.trigger_state.to_label(),
                ),
            )

            ready = self._select_ready_issues(raw_issues)

            append_orchestra_event(
                "dispatcher",
                f"{self.service_name} collect: {len(ready)} ready issues",
            )
            return ready

    async def on_tick(self) -> None:
        """Periodic scan and async dispatch for the configured trigger state.

        **DEPRECATED**: This method bypasses capacity checks and should not be
        called directly. Use GlobalDispatchCoordinator.coordinate() instead,
        which properly checks capacity before emitting dispatch intents.

        This method is kept for backward compatibility but will raise a warning
        if called outside of GlobalDispatchCoordinator context.
        """
        import warnings

        warnings.warn(
            f"{self.service_name}.on_tick() is deprecated: "
            "bypasses capacity checks. Use GlobalDispatchCoordinator instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        ready = await self.collect_ready_issues()

        for issue in ready:
            try:
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} emitting dispatch-intent event "
                    f"for #{issue.number}",
                    level="DEBUG",
                )
                self._emit_dispatch_intent(issue)

                logger.bind(
                    domain="orchestra",
                    trigger=self.role_def.trigger_name,
                    issue=issue.number,
                ).debug("Dispatch-intent event emitted, handler will dispatch")
            except Exception as exc:
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} failed to emit event "
                    f"for #{issue.number}: {exc}",
                )
                logger.bind(
                    domain="orchestra",
                    trigger=self.role_def.trigger_name,
                    issue=issue.number,
                ).warning(f"State dispatch failed: {exc}")

    def _emit_dispatch_intent(self, issue: IssueInfo) -> None:
        from vibe3.domain import publish
        from vibe3.roles.registry import build_label_dispatch_event

        branch, _ = self._flow_context(issue.number)
        publish(
            build_label_dispatch_event(
                self.role_def,
                issue,
                branch=branch,
            )
        )

    def _flow_context(self, issue_number: int) -> tuple[str, dict[str, object] | None]:
        flow = self._flow_manager.get_flow_for_issue(issue_number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        if not branch:
            return "", None
        return branch, self._store.get_flow_state(branch)

    def _select_ready_issues(
        self, raw_issues: list[dict[str, object]]
    ) -> list[IssueInfo]:
        selected: list[IssueInfo] = []
        for item in raw_issues:
            labels = _normalize_labels(item.get("labels"))
            if IssueState.BLOCKED.to_label() in labels:
                continue
            # Skip failed issues - they should not be auto-dispatched
            if IssueState.FAILED.to_label() in labels:
                continue
            if self.role_def.trigger_state.to_label() not in labels:
                continue
            issue = IssueInfo.from_github_payload(item)
            if issue is None:
                continue
            if self.role_def.trigger_name == "manager":
                # Manager is the entry point. Always dispatch if the label is present,
                # unless there's already a live session (handled in _should_dispatch).
                # We don't skip if branch/flow_state is missing because Manager
                # is responsible for creating them.
                branch, flow_state = self._flow_context(issue.number)
                if not self._should_dispatch(issue.number, flow_state):
                    continue
                selected.append(issue)
                continue

            # For downstream roles (plan/run/review), we need a branch to exist.
            branch, flow_state = self._flow_context(issue.number)
            if not branch or not _is_auto_task_branch(branch):
                # If no branch exists yet, we can't dispatch downstream agents.
                # This usually means manager hasn't run yet.
                continue

            # Verify the git branch actually exists, not just a stale flow record.
            # A flow may reference a branch that was deleted (aborted/cleaned up).
            if not self._flow_manager.git.branch_exists(branch):
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} skip #{issue.number}: "
                    f"branch '{branch}' not found in git",
                )
                continue

            if not self._should_dispatch(issue.number, flow_state):
                continue

            selected.append(issue)
        return sort_ready_issues(selected)

    def _should_dispatch(
        self,
        issue_number: int,
        flow_state: dict[str, object] | None,
    ) -> bool:
        """Use role definition's dispatch_predicate with registry liveness check.

        Registry provides accurate liveness verification:
        - Real-time tmux session verification
        - Orphan detection (stale sessions > 60s)
        - Grace period for recent starting sessions

        Simplified: delegate all liveness checking to registry,
        removing redundant flow_state.status_field check.
        """
        has_live_session = self._has_live_dispatch(issue_number)
        return self.role_def.dispatch_predicate(flow_state or {}, has_live_session)

    def _has_live_dispatch(self, issue_number: int) -> bool:
        if self._registry is None:
            raise RuntimeError(
                "SessionRegistryService is required to check live dispatch"
            )

        branch, _ = self._flow_context(issue_number)
        if not branch:
            return False
        sessions = self._registry.get_truly_live_sessions_for_target(
            role=self.role_def.registry_role,
            branch=branch,
            target_id=str(issue_number),
        )
        return len(sessions) > 0
