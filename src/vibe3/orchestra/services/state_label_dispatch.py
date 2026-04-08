"""State-driven trigger service for manager/plan/run/review execution."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.review_runner import format_agent_actor
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.environment.worktree import WorktreeManager
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import (
    STATE_PROGRESS_CONTRACT,
    IssueInfo,
    IssueState,
)
from vibe3.models.review_runner import AgentOptions
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_ordering import sort_ready_issues
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase
from vibe3.runtime.no_progress_policy import (
    execute_state_fallback,
    has_progress_changed,
    snapshot_progress,
)
from vibe3.services.execution_lifecycle import persist_execution_lifecycle_event

if TYPE_CHECKING:
    from vibe3.services.orchestra_status_service import OrchestraStatusService
    from vibe3.services.session_registry import SessionRegistryService

TriggerName = Literal["manager", "plan", "run", "review"]

_TRIGGER_STATUS_FIELD: dict[TriggerName, str | None] = {
    "manager": None,
    "plan": "planner_status",
    "run": "executor_status",
    "review": "reviewer_status",
}

_TRIGGER_EXECUTION_ROLE: dict[
    TriggerName,
    Literal["planner", "executor", "reviewer"] | None,
] = {
    "manager": None,
    "plan": "planner",
    "run": "executor",
    "review": "reviewer",
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


def _current_cli_entry() -> str:
    """Return the canonical CLI entry from the current baseline worktree."""
    return str(Path(__file__).resolve().parents[4] / "src" / "vibe3" / "cli.py")


def _current_repo_root() -> str:
    """Return the canonical repository root for uv project resolution."""
    return str(Path(__file__).resolve().parents[4])


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
        status_service: OrchestraStatusService | None = None,
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
        self._status_service = status_service
        self._manager = manager or ManagerExecutor(config, dry_run=config.dry_run)
        self._backend = CodeagentBackend()
        self._store = SQLiteClient()
        self._runtime_config = VibeConfig.get_defaults()
        self._registry = registry
        self._in_flight_dispatches: set[int] = set()
        self._dispatch_guard = asyncio.Lock()
        self._progress_snapshots: dict[int, dict[str, object]] = {}

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
                ),
            )

            self._prune_in_flight(raw_issues)
            ready = self._select_ready_issues(raw_issues)
            ready_numbers = ", ".join(f"#{issue.number}" for issue in ready) or "(none)"
            append_orchestra_event(
                "dispatcher",
                f"{self.service_name} tick ready issues: {ready_numbers}",
            )

        # Apply capacity limit for manager trigger
        if self.trigger_name == "manager" and ready:
            if self._registry is None:
                raise RuntimeError(
                    "SessionRegistryService is required for capacity check"
                )
            active_count = self._registry.count_live_worker_sessions(role="manager")
            in_flight_count = len(self._in_flight_dispatches)
            remaining_capacity = max(
                0, self.config.max_concurrent_flows - active_count - in_flight_count
            )

            # Dispatch only up to remaining capacity
            to_dispatch = ready[:remaining_capacity]
            throttled = ready[remaining_capacity:]

            if throttled:
                throttled_numbers = [f"#{issue.number}" for issue in throttled]
                logger.bind(
                    domain="orchestra",
                    trigger=self.trigger_name,
                ).info(
                    f"Throttled {len(throttled)} issues due to capacity limit "
                    f"(live={active_count}, in_flight={in_flight_count}, "
                    f"max={self.config.max_concurrent_flows}, "
                    f"remaining={remaining_capacity}): {', '.join(throttled_numbers)}"
                )
                append_orchestra_event(
                    "dispatcher",
                    (
                        f"{self.service_name} throttled {len(throttled)} issues "
                        f"due to capacity limit "
                        f"(live={active_count}, in_flight={in_flight_count}, "
                        f"max={self.config.max_concurrent_flows}, "
                        f"remaining={remaining_capacity}): "
                        f"{', '.join(throttled_numbers)}"
                    ),
                )

            # Log selected issues before dispatch
            if to_dispatch:
                selected_numbers = [f"#{issue.number}" for issue in to_dispatch]
                logger.bind(
                    domain="orchestra",
                    trigger=self.trigger_name,
                ).info(
                    f"Selected {len(to_dispatch)} issues for dispatch: "
                    f"{', '.join(selected_numbers)}"
                )

            ready = to_dispatch

        for issue in ready:
            if issue.number in self._in_flight_dispatches or self._has_live_dispatch(
                issue.number
            ):
                self._in_flight_dispatches.add(issue.number)
                continue
            self._in_flight_dispatches.add(issue.number)
            try:
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} dispatching #{issue.number}",
                )
                await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    self._dispatch_issue,
                    issue,
                )
            except Exception as exc:
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} dispatch failed for #{issue.number}: {exc}",
                )
                logger.bind(
                    domain="orchestra",
                    trigger=self.trigger_name,
                    issue=issue.number,
                ).warning(f"State dispatch failed: {exc}")
                self._in_flight_dispatches.discard(issue.number)

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
                self._progress_snapshots.pop(issue_number, None)
                continue

            flow = self._manager.flow_manager.get_flow_for_issue(issue_number)
            if not flow:
                stale.add(issue_number)
                self._progress_snapshots.pop(issue_number, None)
                continue

            branch = str(flow.get("branch") or "").strip()
            before_snapshot = self._progress_snapshots.get(issue_number)

            if not self._has_live_dispatch(issue_number):
                # Session ended, check for progress
                if before_snapshot:
                    after_snapshot = snapshot_progress(
                        issue_number=issue_number,
                        branch=branch,
                        store=self._store,
                        github=self._github,
                        repo=self.config.repo,
                    )
                    # Use state-specific progress contract to verify execution
                    expected_ref = STATE_PROGRESS_CONTRACT.get(self.trigger_state)
                    # For READY and HANDOFF, we require leaving the state (transition)
                    # to consider it "progressed", per manager.md contract.
                    require_transition = self.trigger_state in {
                        IssueState.READY,
                        IssueState.HANDOFF,
                    }
                    # For ready-manager and handoff-manager paths, closing the issue via
                    # explicit abandon (flow_status=aborted) also counts as valid
                    # progress. This is scoped to manager paths only.
                    allow_close = (
                        self.trigger_name == "manager"
                        and self.trigger_state
                        in {
                            IssueState.READY,
                            IssueState.HANDOFF,
                        }
                    )
                    has_progress = has_progress_changed(
                        before_snapshot,
                        after_snapshot,
                        expected_ref=expected_ref,
                        require_state_transition=require_transition,
                        allow_close_as_progress=allow_close,
                    )
                    if has_progress:
                        # Progress made (including close-as-progress).
                        # If issue was closed, prune from in-flight (no further
                        # processing needed). Otherwise keep in-flight for next
                        # round.
                        if after_snapshot.get("issue_state") == "closed":
                            stale.add(issue_number)
                        self._progress_snapshots.pop(issue_number, None)
                        continue
                    # No progress: execute fallback and add to stale
                    try:
                        execute_state_fallback(
                            issue_number=issue_number,
                            current_labels=labels,
                            github=self._github,
                            source_state=self.trigger_state,
                            repo=self.config.repo,
                        )
                    except Exception as fallback_exc:
                        logger.bind(
                            domain="orchestra",
                            issue=issue_number,
                        ).error(f"Fallback execution failed: {fallback_exc}")
                        # Do not add to stale, let it retry or remain in-flight
                        continue
                # No before_snapshot or no progress after fallback: add to stale
                stale.add(issue_number)
                self._progress_snapshots.pop(issue_number, None)
                continue

            # If still alive, check if state changed externally (though unlikely)
            if self.trigger_state.to_label() not in labels:
                stale.add(issue_number)
                self._progress_snapshots.pop(issue_number, None)

        self._in_flight_dispatches.difference_update(stale)

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
                flow = self._manager.flow_manager.get_flow_for_issue(issue.number)
                if flow:
                    branch = str(flow.get("branch") or "").strip()
                    flow_state = self._store.get_flow_state(branch) if branch else None
                else:
                    branch = ""
                    flow_state = None
                # For handoff resume: only dispatch for canonical task flows
                if self.trigger_state == IssueState.HANDOFF:
                    if not flow:
                        continue
                    if not _is_auto_task_branch(branch):
                        continue
                    if not flow_state:
                        continue
                    if not self._should_dispatch_from_state(issue.number, flow_state):
                        continue
                # For state/ready: no flow check required (manager can start fresh)
                selected.append(issue)
                continue
            flow = self._manager.flow_manager.get_flow_for_issue(issue.number)
            if not flow:
                continue
            branch = str(flow.get("branch") or "").strip()
            if not _is_auto_task_branch(branch):
                continue
            flow_state = self._store.get_flow_state(branch) if branch else None
            if not flow_state:
                continue
            if not self._should_dispatch_from_state(issue.number, flow_state):
                continue
            selected.append(issue)
        # Sort selected issues by queue ordering rules
        # (milestone -> roadmap -> priority)
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
            # For state/ready and state/handoff: dispatch based on registry
            # live session status only. manager_session_id is a legacy field
            # and no longer used for dispatch decisions.
            return not has_live_session
        if self.trigger_name == "plan":
            # Dispatch if no plan_ref AND no live session running.
            # planner_session_id is a resume hint, not a dispatch gate.
            return not flow_state.get("plan_ref") and not has_live_session
        if self.trigger_name == "run":
            # Dispatch if plan_ref exists AND no report_ref AND no live session.
            # executor_session_id is a resume hint, not a dispatch gate.
            return (
                bool(flow_state.get("plan_ref"))
                and not flow_state.get("report_ref")
                and not has_live_session
            )
        # Dispatch if report_ref exists AND no audit_ref AND no live session.
        # reviewer_session_id is a resume hint, not a dispatch gate.
        return (
            bool(flow_state.get("report_ref"))
            and not flow_state.get("audit_ref")
            and not has_live_session
        )

    def _dispatch_issue(self, issue: IssueInfo) -> None:
        # Capture before snapshot for progress detection (unified for all triggers)
        flow = self._manager.flow_manager.get_flow_for_issue(issue.number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        before_snapshot = snapshot_progress(
            issue_number=issue.number,
            branch=branch,
            store=self._store,
            github=self._github,
            repo=self.config.repo,
        )
        self._progress_snapshots[issue.number] = before_snapshot

        if self.trigger_name == "manager":
            dispatched = self._manager.dispatch_manager(issue)
            if not dispatched:
                reason = "dispatch rejected"
                queued_issues: set[int] = getattr(self._manager, "queued_issues", set())
                if issue.number in queued_issues:
                    reason = "deferred due to capacity"
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} deferred #{issue.number} ({reason})",
                )
                self._in_flight_dispatches.discard(issue.number)
                self._progress_snapshots.pop(issue.number, None)
            else:
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} started #{issue.number}",
                )
            return

        if not flow:
            raise RuntimeError(f"No task flow for issue #{issue.number}")
        if not branch:
            raise RuntimeError(f"Flow branch missing for issue #{issue.number}")
        if self.trigger_name != "manager" and not _is_auto_task_branch(branch):
            raise RuntimeError(
                f"State trigger only supports canonical task scenes, got '{branch}'"
            )

        cwd = self._resolve_cwd(issue.number, branch)
        handle = self._backend.start_async_command(
            self._build_command(issue.number),
            execution_name=f"vibe3-{self.trigger_name}-issue-{issue.number}",
            cwd=cwd,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        )
        refs = {
            "issue": str(issue.number),
            "tmux_session": handle.tmux_session,
            "log_path": str(handle.log_path),
            "state": self.trigger_state.value,
        }
        actor = format_agent_actor(self._resolve_agent_options())
        execution_role = _TRIGGER_EXECUTION_ROLE[self.trigger_name]
        if execution_role is not None:
            persist_execution_lifecycle_event(
                self._store,
                branch,
                execution_role,
                "started",
                actor,
                detail=(
                    f"Started async {self.trigger_name} for issue #{issue.number} "
                    f"in tmux session: {handle.tmux_session}"
                ),
                refs=refs,
                extra_state_updates={"latest_actor": actor},
            )
        else:
            self._store.update_flow_state(branch, latest_actor=actor)
        if execution_role is None:
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
        append_orchestra_event(
            "dispatcher",
            (
                f"{self.service_name} started #{issue.number} "
                f"(session={handle.tmux_session}, log={handle.log_path})"
            ),
        )

    def _resolve_cwd(self, issue_number: int, branch: str) -> Path:
        repo_root = getattr(self._manager, "repo_path", None)
        if not isinstance(repo_root, Path):
            repo_root = Path(GitClient().get_git_common_dir()).parent
        cwd, _ = WorktreeManager(self.config, repo_root).resolve_manager_cwd(
            issue_number,
            branch,
        )
        return cwd or repo_root

    def _build_command(self, issue_number: int) -> list[str]:
        cli_entry = _current_cli_entry()
        if self.trigger_name == "plan":
            return [
                "uv",
                "run",
                "--project",
                _current_repo_root(),
                "python",
                "-I",
                cli_entry,
                "plan",
                "--issue",
                str(issue_number),
                "--no-async",
            ]
        if self.trigger_name == "manager":
            # 彻底走向新的 internal 路由
            return [
                "uv",
                "run",
                "--project",
                _current_repo_root(),
                "python",
                "-I",
                cli_entry,
                "internal",
                "manager",
                str(issue_number),
                "--no-async",
            ]
        if self.trigger_name == "run":
            return [
                "uv",
                "run",
                "--project",
                _current_repo_root(),
                "python",
                "-I",
                cli_entry,
                "run",
                "--no-async",
            ]
        return [
            "uv",
            "run",
            "--project",
            _current_repo_root(),
            "python",
            "-I",
            cli_entry,
            "review",
            "base",
            "--no-async",
        ]

    def _resolve_agent_options(self) -> AgentOptions:
        section: Literal["plan", "run", "review"] = self.trigger_name  # type: ignore[assignment]
        return CodeagentExecutionService(self._runtime_config).resolve_agent_options(
            section
        )

    def _has_live_dispatch(self, issue_number: int) -> bool:
        if self._registry is None:
            raise RuntimeError(
                "SessionRegistryService is required to check live dispatch"
            )

        # Map trigger_name to registry role
        registry_role = _TRIGGER_TO_REGISTRY_ROLE.get(
            self.trigger_name, self.trigger_name
        )
        # Use canonical SessionRegistryService API with branch filter
        flow = self._manager.flow_manager.get_flow_for_issue(issue_number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        if not branch:
            return False
        sessions = self._registry.get_truly_live_sessions_for_target(
            role=registry_role,
            branch=branch,
            target_id=str(issue_number),
        )
        return len(sessions) > 0
