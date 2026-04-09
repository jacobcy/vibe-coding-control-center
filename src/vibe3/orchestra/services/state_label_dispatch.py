"""State-driven trigger service for manager/plan/run/review intent emission."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import (
    IssueInfo,
    IssueState,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_ordering import sort_ready_issues
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.environment.session_registry import SessionRegistryService

TriggerName = Literal["manager", "plan", "run", "review"]

_TRIGGER_STATUS_FIELD: dict[TriggerName, str | None] = {
    "manager": None,
    "plan": "planner_status",
    "run": "executor_status",
    "review": "reviewer_status",
}

# Map trigger_name to registry role for live session queries
_TRIGGER_TO_REGISTRY_ROLE: dict[TriggerName, str] = {
    "manager": "manager",
    "plan": "planner",
    "run": "executor",
    "review": "reviewer",
}


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
    """Dispatch manager or downstream agents from issue state labels."""

    event_types: list[str] = []

    @property
    def service_name(self) -> str:
        return f"{type(self).__name__}({self.trigger_name}:{self.trigger_state.value})"

    def __init__(
        self,
        config: OrchestraConfig,
        *,
        trigger_state: IssueState,
        trigger_name: TriggerName,
        github: GitHubClient | None = None,
        executor: ThreadPoolExecutor | None = None,
        manager: ManagerExecutor | None = None,
        registry: "SessionRegistryService | None" = None,
    ) -> None:
        self.config = config
        self.trigger_state = trigger_state
        self.trigger_name: TriggerName = trigger_name
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._github = github or GitHubClient()
        self._manager = manager or ManagerExecutor(config, dry_run=config.dry_run)
        self._store = SQLiteClient()
        self._registry = registry
        self._dispatch_guard = asyncio.Lock()
        self._facade = OrchestrationFacade()

    async def handle_event(self, event: GitHubEvent) -> None:
        return

    async def on_tick(self) -> None:
        """Periodic scan and async dispatch for the configured trigger state."""
        async with self._dispatch_guard:
            raw_issues = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self._github.list_issues(
                    limit=100,
                    state="open",
                    assignee=None,
                    repo=self.config.repo,
                    label=self.trigger_state.to_label(),
                ),
            )

            ready = self._select_ready_issues(raw_issues)
            ready_count = len(ready)

            # Log at INFO level: just the count
            append_orchestra_event(
                "dispatcher",
                f"{self.service_name} tick: {ready_count} ready issues",
            )
            # Log at DEBUG level: full list
            if ready:
                ready_numbers = ", ".join(f"#{issue.number}" for issue in ready)
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} tick ready issues: {ready_numbers}",
                    level="DEBUG",
                )

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
                    trigger=self.trigger_name,
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
                    trigger=self.trigger_name,
                    issue=issue.number,
                ).warning(f"State dispatch failed: {exc}")

    def _emit_dispatch_intent(self, issue: IssueInfo) -> None:
        branch, flow_state = self._flow_context(issue.number)
        if self.trigger_name == "manager":
            self._facade.on_issue_state_changed(issue_info=issue, from_state=None)
            return
        if self.trigger_name == "plan":
            self._facade.on_planner_dispatch(issue_info=issue, branch=branch)
            return
        if self.trigger_name == "run":
            plan_ref = flow_state.get("plan_ref") if flow_state else None
            self._facade.on_executor_dispatch(
                issue_info=issue,
                branch=branch,
                plan_ref=str(plan_ref) if plan_ref else None,
            )
            return
        if self.trigger_name == "review":
            report_ref = flow_state.get("report_ref") if flow_state else None
            self._facade.on_reviewer_dispatch(
                issue_info=issue,
                branch=branch,
                report_ref=str(report_ref) if report_ref else None,
            )
            return
        self._facade.on_issue_state_changed(issue_info=issue, from_state=None)

    def _flow_context(self, issue_number: int) -> tuple[str, dict[str, object] | None]:
        flow = self._manager.flow_manager.get_flow_for_issue(issue_number)
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
            if self.trigger_state.to_label() not in labels:
                continue
            issue = IssueInfo.from_github_payload(item)
            if issue is None:
                continue
            if self.trigger_name == "manager":
                branch, flow_state = self._flow_context(issue.number)
                if self.trigger_state == IssueState.HANDOFF:
                    if (
                        not branch
                        or not _is_auto_task_branch(branch)
                        or not flow_state
                        or not self._should_dispatch_from_state(
                            issue.number, flow_state
                        )
                    ):
                        continue
                selected.append(issue)
                continue
            branch, flow_state = self._flow_context(issue.number)
            if (
                not branch
                or not _is_auto_task_branch(branch)
                or not flow_state
                or not self._should_dispatch_from_state(issue.number, flow_state)
            ):
                continue
            selected.append(issue)
        return sort_ready_issues(selected)

    def _should_dispatch_from_state(
        self,
        issue_number: int,
        flow_state: dict[str, object],
    ) -> bool:
        status_field = _TRIGGER_STATUS_FIELD[self.trigger_name]
        is_running = bool(status_field and flow_state.get(status_field) == "running")
        has_live_session = is_running and self._has_live_dispatch(issue_number)

        if self.trigger_name == "manager":
            return not has_live_session
        if self.trigger_name == "plan":
            return not flow_state.get("plan_ref") and not has_live_session
        if self.trigger_name == "run":
            return (
                bool(flow_state.get("plan_ref"))
                and not flow_state.get("report_ref")
                and not has_live_session
            )
        return (
            bool(flow_state.get("report_ref"))
            and not flow_state.get("audit_ref")
            and not has_live_session
        )

    def _has_live_dispatch(self, issue_number: int) -> bool:
        if self._registry is None:
            raise RuntimeError(
                "SessionRegistryService is required to check live dispatch"
            )

        registry_role = _TRIGGER_TO_REGISTRY_ROLE.get(
            self.trigger_name, self.trigger_name
        )
        branch, _ = self._flow_context(issue_number)
        if not branch:
            return False
        sessions = self._registry.get_truly_live_sessions_for_target(
            role=registry_role,
            branch=branch,
            target_id=str(issue_number),
        )
        return len(sessions) > 0
