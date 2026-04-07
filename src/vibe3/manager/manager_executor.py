"""Unified execution management for Orchestra."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.environment.worktree import WorktreeManager
from vibe3.manager.command_builder import CommandBuilder
from vibe3.manager.flow_manager import FlowManager
from vibe3.manager.result_handler import DispatchResultHandler
from vibe3.manager.session_naming import get_manager_session_name
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.status_service import OrchestraStatusService
from vibe3.runtime.circuit_breaker import CircuitBreaker
from vibe3.runtime.executor import run_command

if TYPE_CHECKING:
    from vibe3.prompts.models import PromptRenderResult
    from vibe3.services.session_registry import SessionRegistryService


class ManagerExecutor:
    """Unified manager for execution context (flow, worktree, agent, results)."""

    def __init__(
        self,
        config: OrchestraConfig,
        repo_path: Path | None = None,
        dry_run: bool = False,
        prompts_path: Path | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        registry: "SessionRegistryService | None" = None,
    ):
        self.config = config
        self.repo_path = repo_path or Path.cwd()
        self.dry_run = dry_run

        self._flow_manager = FlowManager(config, registry=registry)
        self.worktree_manager = WorktreeManager(
            config, self.repo_path, self._flow_manager
        )
        self.command_builder = CommandBuilder(config, prompts_path=prompts_path)
        self.result_handler = DispatchResultHandler(config, self._flow_manager)
        self.status_service = OrchestraStatusService(
            config, orchestrator=self._flow_manager
        )
        self._backend = CodeagentBackend()

        self._registry = registry

        self._circuit_breaker = circuit_breaker
        if self._circuit_breaker is None and config.circuit_breaker.enabled:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=config.circuit_breaker.failure_threshold,
                cooldown_seconds=config.circuit_breaker.cooldown_seconds,
                half_open_max_tests=config.circuit_breaker.half_open_max_tests,
            )

        self._last_error_category: str | None = None
        self._queued_issues: set[int] = set()

    @property
    def flow_manager(self) -> Any:
        return self._flow_manager

    @flow_manager.setter
    def flow_manager(self, value: Any) -> None:
        self._flow_manager = value

    @property
    def queued_issues(self) -> set[int]:
        return self._queued_issues

    @property
    def last_manager_render_result(self) -> "PromptRenderResult | None":
        return self.command_builder.last_manager_render_result

    def _run_command(self, cmd: list[str], cwd: Path, label: str) -> bool:
        """Execute a command via the dispatcher machinery."""
        success, category = run_command(
            cmd, cwd, label, circuit_breaker=self._circuit_breaker
        )
        self._last_error_category = category
        return success

    def _mark_manager_start_failed(self, issue: IssueInfo, reason: str) -> None:
        """Record a manager startup failure as state/failed.

        Also marks the flow as stale so the issue can be re-dispatched
        after the failure is resolved.
        """
        self.result_handler.post_failure_comment(
            issue.number,
            f"Manager 启动失败，已切换为 state/failed。\n\n原因：{reason}",
        )
        self.result_handler.update_state_label(issue.number, IssueState.FAILED)
        # Release the flow lock so issue can be re-dispatched after recovery
        try:
            flow = self._flow_manager.get_flow_for_issue(issue.number)
            if flow and flow.get("branch"):
                self._flow_manager.store.update_flow_state(
                    str(flow["branch"]), flow_status="stale"
                )
        except Exception as exc:
            logger.bind(domain="orchestra", issue=issue.number).warning(
                f"Failed to mark flow stale after start failure: {exc}"
            )

    def dispatch_manager(self, issue: IssueInfo) -> bool:
        """Complete lifecycle for manager dispatch with queuing."""
        log = logger.bind(
            domain="orchestra",
            action="manager_dispatch",
            issue=issue.number,
        )

        if self._registry is None:
            raise RuntimeError(
                "SessionRegistryService is required for manager dispatch"
            )
        active_count = self._registry.count_live_worker_sessions(role="manager")
        capacity = self.config.max_concurrent_flows

        if active_count >= capacity:
            log.warning(
                f"Throttled: Manager capacity reached ({active_count}/{capacity}). "
                f"Queueing #{issue.number}"
            )
            self._queued_issues.add(issue.number)
            return False

        # If it was in queue, remove it now that we are dispatching
        self._queued_issues.discard(issue.number)

        if self.dry_run:
            cmd = self.command_builder.build_manager_command(issue)
            log.info(f"Dry run: skipping flow/worktree/execution. Cmd: {' '.join(cmd)}")
            return True

        try:
            flow = self._flow_manager.create_flow_for_issue(issue)
            flow_branch = str(flow.get("branch") or "").strip()
            if not flow_branch:
                log.error("Flow branch missing")
                self._mark_manager_start_failed(issue, "flow branch missing")
                return False
        except Exception as e:
            log.error(f"Flow creation failed: {e}")
            self._mark_manager_start_failed(issue, f"flow creation failed: {e}")
            return False

        # Worktree preparation
        manager_cwd, is_temporary = self._resolve_manager_cwd(issue.number, flow_branch)
        if not manager_cwd:
            log.error("Unable to resolve worktree")
            self._mark_manager_start_failed(issue, "unable to resolve worktree")
            return False

        if not self.worktree_manager.align_auto_scene_to_base(manager_cwd, flow_branch):
            log.error("Unable to align auto scene to configured base ref")
            self._mark_manager_start_failed(
                issue,
                (
                    "unable to align auto scene to configured base ref "
                    f"({self.config.scene_base_ref})"
                ),
            )
            return False

        log.info(f"Using worktree: {manager_cwd} (temp={is_temporary})")

        # Resolve agent options in dispatcher context (correct worktree/config)
        # and pass to subprocess via env vars to override task-branch config
        from vibe3.config.settings import VibeConfig
        from vibe3.orchestra.agent_resolver import resolve_manager_agent_options

        _manager_options = resolve_manager_agent_options(
            self.config,
            VibeConfig.get_defaults(),
            worktree=False,  # Never use --worktree flag, worktree is self-managed
        )
        _manager_env = {
            **os.environ,
            "VIBE3_ASYNC_CHILD": "1",
        }
        if _manager_options.backend:
            _manager_env["VIBE3_MANAGER_BACKEND"] = _manager_options.backend
        if _manager_options.model:
            _manager_env["VIBE3_MANAGER_MODEL"] = _manager_options.model

        launched = False
        # Reserve session in registry BEFORE launching tmux (prevent orphaned sessions)
        session_id: int | None = None
        if self._registry is not None:
            session_id = self._registry.reserve(
                role="manager",
                target_type="issue",
                target_id=str(issue.number),
                branch=flow_branch,
            )

        try:
            cmd = [
                "uv",
                "run",
                "--project",
                str(self.repo_path),
                "python",
                "-I",
                str(self._resolve_cli_entry()),
                "run",
                "--manager-issue",
                str(issue.number),
                "--sync",
            ]
            try:
                handle = self._backend.start_async_command(
                    cmd,
                    execution_name=get_manager_session_name(issue.number),
                    cwd=manager_cwd,
                    env=_manager_env,
                )
            except Exception as exc:
                # Clean up reserved session on launch failure
                if self._registry is not None and session_id is not None:
                    self._registry.mark_failed(session_id)
                log.error(f"Manager async start failed: {exc}")
                self._mark_manager_start_failed(
                    issue,
                    f"manager async start failed: {exc}",
                )
                return False
            log.info(
                f"Started manager async session: {handle.tmux_session} "
                f"(log: {handle.log_path})"
            )
            launched = True

            # Mark session as running AFTER successful launch
            if self._registry is not None and session_id is not None:
                try:
                    self._registry.mark_started(
                        session_id, tmux_session=handle.tmux_session
                    )
                except Exception as exc:
                    # Database error, but tmux is already running
                    # Log warning but don't fail the dispatch
                    log.warning(
                        f"Failed to mark session started in registry: {exc}. "
                        "Session will be cleaned up by reconcile."
                    )

            self._flow_manager.store.add_event(
                flow_branch,
                "manager_dispatched",
                "system",
                detail=(
                    f"Dispatched manager to tmux session: {handle.tmux_session}\n"
                    f"Log: {handle.log_path}"
                ),
                refs={
                    "tmux_session": handle.tmux_session,
                    "log_path": str(handle.log_path),
                    "issue": str(issue.number),
                },
            )
            # Only record launch; child records its own lifecycle events
            return True
        finally:
            if is_temporary and manager_cwd:
                if launched:
                    log.info(
                        f"Preserving newly dispatched manager worktree at {manager_cwd}"
                    )
                elif self._should_recycle(issue.number):
                    self.worktree_manager.recycle(manager_cwd)
                else:
                    log.info(
                        f"Preserving worktree at {manager_cwd} "
                        "(issue still in-progress)"
                    )

    def dispatch_pr_review(self, pr_number: int) -> bool:
        """Complete lifecycle for PR review dispatch with queuing."""
        log = logger.bind(
            domain="orchestra",
            action="review_dispatch",
            pr_number=pr_number,
        )

        active_count = self.status_service.get_active_flow_count()
        capacity = self.config.max_concurrent_flows

        if active_count >= capacity:
            log.warning(
                f"Throttled: Capacity reached ({active_count}/{capacity}). "
                f"Queueing review for #{pr_number}"
            )
            # Use negative numbers for PRs in queue
            self._queued_issues.add(-pr_number)
            return False

        self._queued_issues.discard(-pr_number)

        cmd = self.command_builder.build_pr_review_command(pr_number)

        review_cwd = self._resolve_review_cwd_for_dispatch(pr_number)

        log.info(f"Dispatching review: {' '.join(cmd)} (cwd={review_cwd})")

        if self.dry_run:
            log.info("Dry run, skipping execution")
            return True

        return self._run_command(cmd, review_cwd, "Review execution")

    def _resolve_review_cwd_for_dispatch(self, pr_number: int) -> Path:
        """Helper to resolve PR review cwd based on config."""
        if self.config.pr_review_dispatch.use_worktree:
            return self.repo_path
        return self._resolve_review_cwd(pr_number)

    def _resolve_cli_entry(self) -> Path:
        """Return the canonical CLI entry in the current baseline worktree."""
        return (self.repo_path / "src" / "vibe3" / "cli.py").resolve()

    def _should_recycle(self, issue_number: int) -> bool:
        """Decide if we should recycle the worktree now."""
        try:
            from vibe3.services.label_service import LabelService

            state = LabelService(repo=self.config.repo).get_state(issue_number)
            return state not in {
                IssueState.CLAIMED,
                IssueState.IN_PROGRESS,
                IssueState.HANDOFF,
                IssueState.REVIEW,
                IssueState.MERGE_READY,
            }
        except Exception:
            return False

    # --- Methods that delegate to worktree_manager, allowing subclass override ---

    def _resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> tuple[Path | None, bool]:
        return self.worktree_manager._resolve_manager_cwd(issue_number, flow_branch)

    def _normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        return self.worktree_manager._normalize_manager_command(cmd, cwd)

    def _ensure_manager_worktree(
        self, issue_number: int, branch: str
    ) -> tuple[Path | None, bool]:
        return self.worktree_manager._ensure_manager_worktree(issue_number, branch)

    def _resolve_review_cwd(self, pr_number: int) -> Path:
        return self.worktree_manager._resolve_review_cwd(pr_number)
