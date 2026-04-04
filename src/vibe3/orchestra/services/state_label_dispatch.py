"""State-driven trigger service for plan/run/review execution."""

from __future__ import annotations

import asyncio
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend, extract_session_id
from vibe3.agents.review_runner import format_agent_actor
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.manager.worktree_manager import WorktreeManager
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.review_runner import AgentOptions
from vibe3.orchestra.config import OrchestraConfig
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.orchestra.services.status_service import OrchestraStatusService

TriggerName = Literal["plan", "run", "review"]


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


class StateLabelDispatchService(ServiceBase):
    """Dispatch downstream agents from issue state labels."""

    event_types: list[str] = []

    def __init__(
        self,
        config: OrchestraConfig,
        *,
        trigger_state: IssueState,
        trigger_name: TriggerName,
        github: GitHubClient | None = None,
        executor: ThreadPoolExecutor | None = None,
        status_service: "OrchestraStatusService" | None = None,
        manager: ManagerExecutor | None = None,
    ) -> None:
        self.config = config
        self.trigger_state = trigger_state
        self.trigger_name = trigger_name
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._github = github or GitHubClient()
        self._status_service = status_service
        self._manager = manager or ManagerExecutor(config, dry_run=config.dry_run)
        self._backend = CodeagentBackend()
        self._store = SQLiteClient()
        self._runtime_config = VibeConfig.get_defaults()
        self._in_flight_dispatches: set[int] = set()
        self._dispatch_guard = asyncio.Lock()

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
                ),
            )
            if self._has_open_failed_issue(raw_issues):
                logger.bind(
                    domain="orchestra",
                    trigger=self.trigger_name,
                ).warning("Pause state trigger: open state/failed issue exists")
                return

            self._prune_in_flight(raw_issues)
            ready = self._select_ready_issues(raw_issues)
            for issue in ready:
                if issue.number in self._in_flight_dispatches:
                    continue
                self._in_flight_dispatches.add(issue.number)
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        self._executor,
                        self._dispatch_issue,
                        issue,
                    )
                except Exception as exc:
                    logger.bind(
                        domain="orchestra",
                        trigger=self.trigger_name,
                        issue=issue.number,
                    ).warning(f"State dispatch failed: {exc}")
                    self._in_flight_dispatches.discard(issue.number)

    def _has_open_failed_issue(self, raw_issues: list[dict[str, object]]) -> bool:
        return any(
            IssueState.FAILED.to_label() in _normalize_labels(item.get("labels"))
            for item in raw_issues
        )

    def _prune_in_flight(self, raw_issues: list[dict[str, object]]) -> None:
        states_by_issue = {
            item["number"]: _normalize_labels(item.get("labels"))
            for item in raw_issues
            if isinstance(item.get("number"), int)
        }
        stale: set[int] = set()
        for issue_number in self._in_flight_dispatches:
            labels = states_by_issue.get(issue_number, [])
            if self.trigger_state.to_label() not in labels:
                stale.add(issue_number)
                continue
            flow = self._manager.flow_manager.get_flow_for_issue(issue_number)
            if not flow:
                stale.add(issue_number)
                continue
            branch = str(flow.get("branch") or "").strip()
            flow_state = self._store.get_flow_state(branch) if branch else None
            if not flow_state or not self._should_dispatch_from_state(flow_state):
                stale.add(issue_number)
        self._in_flight_dispatches.difference_update(stale)

    def _select_ready_issues(
        self, raw_issues: list[dict[str, object]]
    ) -> list[IssueInfo]:
        selected: list[IssueInfo] = []
        for item in raw_issues:
            labels = _normalize_labels(item.get("labels"))
            if self.trigger_state.to_label() not in labels:
                continue
            issue = IssueInfo.from_github_payload(item)
            if issue is None:
                continue
            flow = self._manager.flow_manager.get_flow_for_issue(issue.number)
            if not flow:
                continue
            branch = str(flow.get("branch") or "").strip()
            flow_state = self._store.get_flow_state(branch) if branch else None
            if not flow_state:
                continue
            if not self._should_dispatch_from_state(flow_state):
                continue
            selected.append(issue)
        return selected

    def _should_dispatch_from_state(self, flow_state: dict[str, object]) -> bool:
        if self.trigger_name == "plan":
            return not flow_state.get("plan_ref") and not flow_state.get(
                "planner_session_id"
            )
        if self.trigger_name == "run":
            return (
                bool(flow_state.get("plan_ref"))
                and not flow_state.get("report_ref")
                and not flow_state.get("executor_session_id")
            )
        return (
            bool(flow_state.get("report_ref"))
            and not flow_state.get("audit_ref")
            and not flow_state.get("reviewer_session_id")
        )

    def _dispatch_issue(self, issue: IssueInfo) -> None:
        flow = self._manager.flow_manager.get_flow_for_issue(issue.number)
        if not flow:
            raise RuntimeError(f"No task flow for issue #{issue.number}")
        branch = str(flow.get("branch") or "").strip()
        if not branch:
            raise RuntimeError(f"Flow branch missing for issue #{issue.number}")

        cwd = self._resolve_cwd(issue.number, branch)
        handle = self._backend.start_async_command(
            self._build_command(issue.number),
            execution_name=f"vibe3-{self.trigger_name}-issue-{issue.number}",
            cwd=cwd,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        )
        session_id = self._wait_for_async_session_id(handle.log_path)
        refs = {
            "issue": str(issue.number),
            "tmux_session": handle.tmux_session,
            "log_path": str(handle.log_path),
            "state": self.trigger_state.value,
        }
        updates: dict[str, object] = {
            "latest_actor": format_agent_actor(self._resolve_agent_options()),
        }
        if session_id:
            refs["session_id"] = session_id
            updates[self._session_field()] = session_id
        self._store.update_flow_state(branch, **updates)
        self._store.add_event(
            branch,
            f"{self.trigger_name}_dispatched",
            "orchestra:state-trigger",
            detail=(
                f"Triggered {self.trigger_name} for issue #{issue.number} "
                f"from {self.trigger_state.to_label()}"
            ),
            refs=refs,
        )

    def _resolve_cwd(self, issue_number: int, branch: str) -> Path:
        repo_root = Path(GitClient().get_git_common_dir()).parent
        cwd, _ = WorktreeManager(self.config, repo_root).resolve_manager_cwd(
            issue_number,
            branch,
        )
        return cwd or repo_root

    def _build_command(self, issue_number: int) -> list[str]:
        if self.trigger_name == "plan":
            return [
                "uv",
                "run",
                "python",
                "src/vibe3/cli.py",
                "plan",
                "issue",
                str(issue_number),
                "--sync",
            ]
        if self.trigger_name == "run":
            return [
                "uv",
                "run",
                "python",
                "src/vibe3/cli.py",
                "run",
                "--sync",
            ]
        return [
            "uv",
            "run",
            "python",
            "src/vibe3/cli.py",
            "review",
            "base",
            "--sync",
        ]

    def _resolve_agent_options(self) -> AgentOptions:
        section: Literal["plan", "run", "review"] = self.trigger_name
        return CodeagentExecutionService(self._runtime_config).resolve_agent_options(
            section
        )

    def _session_field(self) -> str:
        return {
            "plan": "planner_session_id",
            "run": "executor_session_id",
            "review": "reviewer_session_id",
        }[self.trigger_name]

    def _wait_for_async_session_id(
        self, log_path: Path, *, timeout_seconds: float = 10.0
    ) -> str | None:
        """Poll repo and wrapper logs for a session id."""
        wrapper_log_path: Path | None = None
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if log_path.exists():
                try:
                    repo_log_text = log_path.read_text()
                except OSError:
                    repo_log_text = ""
                session_id = extract_session_id(repo_log_text)
                if session_id:
                    return session_id
                if wrapper_log_path is None:
                    match = re.search(
                        r"Log:\s*(\S+codeagent-wrapper-\d+\.log)",
                        repo_log_text,
                    )
                    if match:
                        wrapper_log_path = Path(match.group(1))
            if wrapper_log_path and wrapper_log_path.exists():
                try:
                    wrapper_log_text = wrapper_log_path.read_text()
                except OSError:
                    wrapper_log_text = ""
                session_id = extract_session_id(wrapper_log_text)
                if session_id:
                    return session_id
            time.sleep(0.1)
        return None
