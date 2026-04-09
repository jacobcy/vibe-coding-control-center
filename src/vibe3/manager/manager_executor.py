"""Unified execution management for Orchestra."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.environment.worktree import WorktreeManager
from vibe3.manager.command_builder import CommandBuilder
from vibe3.manager.flow_manager import FlowManager
from vibe3.manager.session_naming import get_manager_session_name
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo
from vibe3.runtime.circuit_breaker import CircuitBreaker
from vibe3.services.issue_failure_service import fail_manager_issue

if TYPE_CHECKING:
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.prompts.models import PromptRenderResult


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
        self._backend = CodeagentBackend()

        self._registry = registry

        self._circuit_breaker = circuit_breaker
        if self._circuit_breaker is None and config.circuit_breaker.enabled:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=config.circuit_breaker.failure_threshold,
                cooldown_seconds=config.circuit_breaker.cooldown_seconds,
                half_open_max_tests=config.circuit_breaker.half_open_max_tests,
            )

        self._active_dispatch_locks: set[int] = set()

    @property
    def flow_manager(self) -> Any:
        return self._flow_manager

    @flow_manager.setter
    def flow_manager(self, value: Any) -> None:
        self._flow_manager = value

    @property
    def last_manager_render_result(self) -> "PromptRenderResult | None":
        return self.command_builder.last_manager_render_result

    def _mark_manager_start_failed(self, issue: IssueInfo, reason: str) -> None:
        """Record a manager startup failure as state/failed.

        Also marks the flow as stale so the issue can be re-dispatched
        after the failure is resolved.
        """
        fail_manager_issue(
            issue_number=issue.number,
            reason=f"Manager 启动失败: {reason}",
            actor="orchestra:manager",
        )
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

        if issue.number in self._active_dispatch_locks:
            log.debug("Skip: Issue already being dispatched by another worker")
            return False

        self._active_dispatch_locks.add(issue.number)
        try:
            return self._dispatch_manager_impl(issue)
        finally:
            self._active_dispatch_locks.discard(issue.number)

    def _dispatch_manager_impl(self, issue: IssueInfo) -> bool:
        """Internal implementation of manager dispatch."""
        log = logger.bind(
            domain="orchestra",
            action="manager_dispatch",
            issue=issue.number,
        )

        if self._registry is None:
            raise RuntimeError(
                "SessionRegistryService is required for manager dispatch"
            )

        # Final pre-flight: check if system is frozen before doing any work
        from vibe3.orchestra.failed_gate import FailedGate

        gate = FailedGate(repo=self.config.repo)
        if gate.check().blocked:
            log.warning("Skip: System is frozen by another failed issue")
            return False

        # Note: Capacity check moved to StateLabelDispatchService
        # ManagerExecutor assumes caller has already verified capacity

        if self.dry_run:
            cmd = self.command_builder.build_manager_command(issue)
            log.info(f"Dry run: skipping flow/worktree/execution. Cmd: {' '.join(cmd)}")
            return True

        try:
            # 1. Flow management
            flow = self._flow_manager.create_flow_for_issue(issue)
            flow_branch = str(flow.get("branch") or "").strip()
            if not flow_branch:
                raise RuntimeError("flow branch missing")

            # 2. Worktree preparation
            manager_cwd, is_temporary = self._resolve_manager_cwd(
                issue.number, flow_branch
            )
            if not manager_cwd:
                raise RuntimeError("unable to resolve worktree")

            if not self.worktree_manager.align_auto_scene_to_base(
                manager_cwd, flow_branch
            ):
                raise RuntimeError(
                    f"failed to align auto scene to {self.config.scene_base_ref}"
                )

            log.info(f"Using worktree: {manager_cwd} (temp={is_temporary})")

            # 3. Resolve agent options
            from vibe3.config.settings import VibeConfig
            from vibe3.runtime.agent_resolver import resolve_manager_agent_options

            _manager_options = resolve_manager_agent_options(
                self.config,
                VibeConfig.get_defaults(),
            )
            _manager_env = {
                **os.environ,
                "VIBE3_ASYNC_CHILD": "1",
            }
            if _manager_options.backend:
                _manager_env["VIBE3_MANAGER_BACKEND"] = _manager_options.backend
            if _manager_options.model:
                _manager_env["VIBE3_MANAGER_MODEL"] = _manager_options.model

            # 4. Dispatch via execution coordinator
            from vibe3.execution.contracts import ExecutionRequest
            from vibe3.execution.coordinator import ExecutionCoordinator

            cmd = [
                "uv",
                "run",
                "--project",
                str(self.repo_path),
                "python",
                "-I",
                str(self._resolve_cli_entry()),
                "internal",
                "manager",
                str(issue.number),
                "--no-async",
            ]

            request = ExecutionRequest(
                role="manager",
                target_branch=flow_branch,
                target_id=issue.number,
                execution_name=get_manager_session_name(issue.number),
                cmd=cmd,
                cwd=str(manager_cwd),
                env=_manager_env,
                refs={"issue": str(issue.number)},
                actor="system",
                mode="async",
            )

            coordinator = ExecutionCoordinator(
                config=self.config,
                store=self._flow_manager.store,
                backend=self._backend,
            )

            result = coordinator.dispatch_execution(request)

            if not result.launched:
                raise RuntimeError(
                    result.reason or "Failed to launch manager execution"
                )

            return True

        except Exception as exc:
            log.error(f"Dispatch failed: {exc}")
            self._mark_manager_start_failed(issue, str(exc))
            return False

    def _resolve_cli_entry(self) -> Path:
        """Return the canonical CLI entry in the current baseline worktree."""
        return (self.repo_path / "src" / "vibe3" / "cli.py").resolve()

    # --- Methods that delegate to worktree_manager, allowing subclass override ---

    def _resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> tuple[Path | None, bool]:
        return self.worktree_manager._resolve_manager_cwd(issue_number, flow_branch)
