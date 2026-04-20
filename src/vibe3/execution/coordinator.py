"""Unified execution coordinator."""

import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

from vibe3.agents.backends.async_launcher import start_async_command
from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.environment.worktree import WorktreeManager
from vibe3.execution.capacity_service import CapacityService
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest
from vibe3.execution.execution_lifecycle import execution_prefix
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.logging import append_orchestra_event


class ExecutionCoordinator:
    """Coordinator for launching and tracking role executions."""

    def __init__(
        self,
        config: OrchestraConfig,
        store: SQLiteClient,
        backend: Optional[CodeagentBackend] = None,
        capacity: Optional[CapacityService] = None,
    ) -> None:
        """Initialize the execution coordinator."""
        self.config = config
        self.store = store
        self.backend = backend or CodeagentBackend()
        self.capacity = capacity or CapacityService(config, store, self.backend)
        self.registry = SessionRegistryService(store, self.backend)

    def _resolve_cwd(self, request: ExecutionRequest) -> Optional[Path]:
        """Resolve execution cwd from explicit request or environment policy."""
        if request.cwd:
            return Path(request.cwd)

        if request.worktree_requirement == WorktreeRequirement.NONE:
            return None

        if request.worktree_requirement == WorktreeRequirement.TEMPORARY:
            return self._acquire_temporary_worktree(request.target_id)

        if request.worktree_requirement != WorktreeRequirement.PERMANENT:
            raise ValueError(
                f"Unsupported worktree requirement: {request.worktree_requirement}"
            )

        # Resolve repo_path: prefer explicit request, then git common dir (main repo)
        # Using git common dir prevents creating worktrees inside current worktree
        if request.repo_path:
            repo_path = Path(request.repo_path)
        else:
            from vibe3.clients.git_client import GitClient

            try:
                git_common = GitClient().get_git_common_dir()
                repo_path = Path(git_common).parent if git_common else Path.cwd()
            except Exception:
                repo_path = Path.cwd()

        worktree_manager = WorktreeManager(self.config, repo_path)
        manager_cwd, _ = worktree_manager.resolve_manager_cwd(
            request.target_id,
            request.target_branch,
        )
        if manager_cwd is None:
            raise ValueError(
                f"Failed to resolve permanent worktree for "
                f"{request.role}:{request.target_id}"
            )
        return manager_cwd

    def _acquire_temporary_worktree(self, issue_number: int) -> Path:
        """Acquire a temporary worktree for supervisor apply execution.

        The worktree persists for the duration of the async execution.
        It is cleaned up automatically on the next dispatch for the same issue.
        """
        from vibe3.clients.git_client import GitClient

        try:
            git_common = GitClient().get_git_common_dir()
            repo_path = Path(git_common).parent if git_common else Path.cwd()
        except Exception:
            repo_path = Path.cwd()

        worktree_manager = WorktreeManager(self.config, repo_path)
        ctx = worktree_manager.acquire_temporary_worktree(
            issue_number=issue_number,
            base_branch="main",
        )
        return ctx.path

    @staticmethod
    def _resolve_runtime_target(request: ExecutionRequest) -> tuple[str, str]:
        """Map an execution request to runtime-session target identifiers."""
        target_branch = request.target_branch or ""
        target_id = str(request.target_id)
        if target_branch.startswith("task/issue-") or target_branch.startswith(
            "issue-"
        ):
            return ("issue", target_id)
        return ("branch", target_branch or target_id)

    @staticmethod
    @contextmanager
    def _without_async_child_marker(enabled: bool) -> Generator[None, None, None]:
        """Keep the async-child marker scoped to outer coordinator logic only."""
        if not enabled:
            yield
            return

        previous = os.environ.pop("VIBE3_ASYNC_CHILD", None)
        try:
            yield
        finally:
            if previous is not None:
                os.environ["VIBE3_ASYNC_CHILD"] = previous

    def dispatch_execution(self, request: ExecutionRequest) -> ExecutionLaunchResult:
        """Dispatch an execution request.

        Two dispatch modes:

        Container-inside (sync): All roles run through
        CodeagentExecutionService, which handles handoff,
        pre-gate callbacks, gate, and lifecycle uniformly.

        Container-outside (async): Launches a tmux session and returns
        immediately. The tmux child then re-enters the same sync shell.
        `VIBE3_ASYNC_CHILD` is scoped to the outer wrapper guards only.
        Coordinator may record a tmux-start checkpoint, but it does not own
        execution lifecycle.

        Simple dispatch model:
        1. Check capacity -> skip if full
        2. Reserve runtime_session for async wrappers
        3. Launch execution
        """
        logger.bind(
            domain="execution_coordinator",
            role=request.role,
            target_id=request.target_id,
            target_branch=request.target_branch,
        ).info(f"Received execution request for {request.role}")

        # Async self-invocation launches a tmux wrapper first, then executes the
        # real sync workload inside that child process. The wrapper already owns
        # the runtime_session row, so the child must not short-circuit on the
        # parent's live-session entry or it will exit immediately without doing
        # any work.
        is_async_child_sync = request.mode == "sync" and (
            os.environ.get("VIBE3_ASYNC_CHILD") == "1"
        )
        runtime_session_id: int | None = None

        # 1. Check capacity
        # Async child sync: outer wrapper already reserved capacity and registered
        # the runtime_session; child must not re-check or it double-counts itself.
        if not is_async_child_sync:
            if not self.capacity.can_dispatch(request.role):
                return ExecutionLaunchResult(
                    launched=False,
                    reason=f"Capacity full for {request.role}",
                    reason_code="capacity_full",
                )

            # 1b. Dispatch dedup: skip if a live session already exists for
            # the same role + branch + target. This prevents the same issue
            # from spawning concurrent duplicate executions.
            if request.target_branch:
                target_type, runtime_target_id = self._resolve_runtime_target(request)
                live = self.registry.get_truly_live_sessions_for_target(
                    role=request.role,
                    branch=request.target_branch,
                    target_id=runtime_target_id,
                )
                if live:
                    logger.bind(
                        domain="execution_coordinator",
                        role=request.role,
                        target_branch=request.target_branch,
                        target_id=runtime_target_id,
                        live_count=len(live),
                    ).info(
                        f"Skipping duplicate dispatch for {request.role} "
                        f"on {request.target_branch}"
                    )
                    return ExecutionLaunchResult(
                        launched=False,
                        reason=(
                            f"Live session already exists for "
                            f"{request.role}/{request.target_branch}"
                        ),
                        reason_code="duplicate_dispatch",
                    )

        try:
            # 2. Launch
            cwd_path = self._resolve_cwd(request)
            env = request.env or dict(os.environ)

            # Launch async
            if request.mode == "async":
                if request.target_branch:
                    target_type, runtime_target_id = self._resolve_runtime_target(
                        request
                    )
                    runtime_session_id = self.registry.reserve(
                        role=request.role,
                        target_type=target_type,
                        target_id=runtime_target_id,
                        branch=request.target_branch,
                    )

                if request.cmd:
                    handle = start_async_command(
                        request.cmd,
                        execution_name=request.execution_name,
                        cwd=cwd_path,
                        env=env,
                    )
                elif request.prompt and request.options is not None:
                    keep_alive = int(request.refs.get("keep_alive_seconds", "0"))
                    task = request.refs.get("task")
                    session_id = request.refs.get("session_id")
                    handle = self.backend.start_async(
                        prompt=request.prompt,
                        options=request.options,
                        task=task,
                        session_id=session_id,
                        execution_name=request.execution_name,
                        cwd=cwd_path,
                        env=env,
                        keep_alive_seconds=keep_alive,
                    )
                else:
                    raise ValueError("Either cmd or prompt+options must be provided")

                tmux_session = handle.tmux_session
                log_path = str(handle.log_path)

                if runtime_session_id is not None:
                    self.registry.mark_started(
                        runtime_session_id,
                        tmux_session=tmux_session,
                        log_path=log_path,
                    )

                if request.target_branch:
                    checkpoint_refs = dict(request.refs)
                    checkpoint_refs["tmux_session"] = tmux_session
                    checkpoint_refs["log_path"] = log_path
                    self.store.add_event(
                        request.target_branch,
                        f"tmux_{execution_prefix(request.role)}_started",  # type: ignore[arg-type]
                        request.actor,
                        detail=f"{request.role.capitalize()} tmux wrapper started",
                        refs=checkpoint_refs,
                    )

                logger.bind(
                    domain="execution_coordinator",
                    role=request.role,
                    target_id=request.target_id,
                    tmux_session=tmux_session,
                ).success(f"Execution launched for {request.role}")

                return ExecutionLaunchResult(
                    launched=True,
                    tmux_session=tmux_session,
                    log_path=log_path,
                )
            elif request.mode == "sync":
                # Ensure we have what we need for sync
                if not request.prompt or request.options is None:
                    raise ValueError("Sync execution requires prompt and options")

                with self._without_async_child_marker(is_async_child_sync):
                    result = CodeagentExecutionService().execute_sync_request(
                        request,
                        cwd=cwd_path,
                    )
                if result.success:
                    return ExecutionLaunchResult(
                        launched=True,
                        stdout=result.stdout,
                    )
                error_msg = result.stderr or "Execution failed"
                append_orchestra_event(
                    "dispatcher",
                    f"{request.role} sync execution failed for #{request.target_id}: "
                    f"{error_msg}",
                )
                return ExecutionLaunchResult(
                    launched=False,
                    reason=error_msg,
                    reason_code="launch_failed",
                )
            else:
                raise ValueError(f"Unknown mode: {request.mode}")

        except Exception as exc:
            error_msg = self._format_launch_error(exc)
            if request.mode == "async" and runtime_session_id is not None:
                self.registry.mark_failed(runtime_session_id)
            append_orchestra_event(
                "dispatcher",
                f"{request.role} launch failed for #{request.target_id}: {error_msg}",
            )
            logger.bind(
                domain="execution_coordinator",
                role=request.role,
                target_id=request.target_id,
            ).error(f"Execution launch failed: {error_msg}")

            return ExecutionLaunchResult(
                launched=False,
                reason=error_msg,
                reason_code="launch_failed",
            )

    @staticmethod
    def _format_launch_error(exc: Exception) -> str:
        """Add context for known launch-failure patterns."""
        error_msg = str(exc)
        match = re.search(r"Tmux session '([^']+)' already exists", error_msg)
        if match:
            session_name = match.group(1)
            return (
                f"{error_msg} (previous session still alive: {session_name}; "
                "launch skipped to avoid duplicate worker)"
            )
        return error_msg
