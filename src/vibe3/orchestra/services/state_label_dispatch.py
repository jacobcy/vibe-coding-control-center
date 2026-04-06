"""State-driven trigger service for manager/plan/run/review execution."""

from __future__ import annotations

import asyncio
import os
import subprocess
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
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.manager.session_naming import get_trigger_session_prefix
from vibe3.manager.worktree_manager import WorktreeManager
from vibe3.models.orchestration import (
    STATE_PROGRESS_CONTRACT,
    IssueInfo,
    IssueState,
)
from vibe3.models.review_runner import AgentOptions
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.no_progress_policy import (
    execute_state_fallback,
    has_progress_changed,
    snapshot_progress,
)
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.orchestra.services.status_service import OrchestraStatusService

TriggerName = Literal["manager", "plan", "run", "review"]


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

        # Apply capacity limit for manager trigger
        if self.trigger_name == "manager" and ready:
            # Calculate effective remaining capacity
            active_count = (
                self._status_service.get_active_flow_count()
                if self._status_service
                else 0
            )
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
                    f"(active={active_count}, in_flight={in_flight_count}, "
                    f"max={self.config.max_concurrent_flows}, "
                    f"remaining={remaining_capacity}): {', '.join(throttled_numbers)}"
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
                    # For ready-manager path, closing the issue also counts as valid
                    # progress. This is scoped to ready only and does not apply to
                    # handoff.
                    allow_close = (
                        self.trigger_state == IssueState.READY
                        and self.trigger_name == "manager"
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
                    if (
                        flow_state
                        and flow_state.get("manager_session_id")
                        and not self._has_live_dispatch(issue.number)
                    ):
                        self._store.update_flow_state(branch, manager_session_id=None)
                        self._store.add_event(
                            branch,
                            "manager_session_cleared",
                            "system",
                            detail=(
                                f"Cleared stale manager session for "
                                f"issue #{issue.number}"
                            ),
                            refs={"issue": str(issue.number)},
                        )
                        flow_state = {
                            **flow_state,
                            "manager_session_id": None,
                        }
                # For handoff resume: only dispatch for canonical task flows
                if self.trigger_state == IssueState.HANDOFF:
                    if not flow:
                        continue
                    if not _is_auto_task_branch(branch):
                        continue
                    if not flow_state:
                        continue
                    if not self._should_dispatch_from_state(flow_state):
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
            if not self._should_dispatch_from_state(flow_state):
                continue
            selected.append(issue)
        return selected

    def _should_dispatch_from_state(self, flow_state: dict[str, object]) -> bool:
        if self.trigger_name == "manager":
            # For state/ready: dispatch if no manager session
            # For state/handoff: dispatch if no manager session.
            # We allow manager to re-triage even if refs (like plan_ref) are missing
            # (e.g. after a no-op fallback from planner/executor).
            return not flow_state.get("manager_session_id")
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
                self._in_flight_dispatches.discard(issue.number)
                self._progress_snapshots.pop(issue.number, None)
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
        updates: dict[str, object] = {
            "latest_actor": format_agent_actor(self._resolve_agent_options()),
        }
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
        cli_entry = _current_cli_entry()
        if self.trigger_name == "plan":
            return [
                "uv",
                "run",
                "python",
                "-I",
                cli_entry,
                "plan",
                "--issue",
                str(issue_number),
                "--sync",
            ]
        if self.trigger_name == "manager":
            return [
                "uv",
                "run",
                "python",
                "-I",
                cli_entry,
                "run",
                "--manager-issue",
                str(issue_number),
                "--sync",
            ]
        if self.trigger_name == "run":
            return [
                "uv",
                "run",
                "python",
                "-I",
                cli_entry,
                "run",
                "--sync",
            ]
        return [
            "uv",
            "run",
            "python",
            "-I",
            cli_entry,
            "review",
            "base",
            "--sync",
        ]

    def _resolve_agent_options(self) -> AgentOptions:
        section: Literal["plan", "run", "review"] = self.trigger_name  # type: ignore[assignment]
        return CodeagentExecutionService(self._runtime_config).resolve_agent_options(
            section
        )

    def _session_field(self) -> str:
        return {
            "manager": "manager_session_id",
            "plan": "planner_session_id",
            "run": "executor_session_id",
            "review": "reviewer_session_id",
        }[self.trigger_name]

    def _has_live_dispatch(self, issue_number: int) -> bool:
        session_prefix = get_trigger_session_prefix(self.trigger_name, issue_number)
        try:
            result = subprocess.run(
                ["tmux", "ls"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError:
            return False
        except Exception:
            return False
        if result.returncode != 0:
            return False
        for line in result.stdout.splitlines():
            session_name = line.split(":", 1)[0].strip()
            if session_name == session_prefix or session_name.startswith(
                f"{session_prefix}-"
            ):
                return True
        return False
