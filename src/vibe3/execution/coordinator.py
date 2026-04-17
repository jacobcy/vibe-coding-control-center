"""Unified execution coordinator."""

import os
from pathlib import Path
from typing import Optional

from loguru import logger

from vibe3.agents.backends.async_launcher import start_async_command
from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.environment.worktree import WorktreeManager
from vibe3.execution.capacity_service import CapacityService
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest
from vibe3.execution.execution_lifecycle import ExecutionLifecycleService
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestra_config import OrchestraConfig


class ExecutionCoordinator:
    """Coordinator for launching and tracking role executions."""

    def __init__(
        self,
        config: OrchestraConfig,
        store: SQLiteClient,
        backend: Optional[CodeagentBackend] = None,
        capacity: Optional[CapacityService] = None,
        lifecycle: Optional[ExecutionLifecycleService] = None,
    ) -> None:
        """Initialize the execution coordinator."""
        self.config = config
        self.store = store
        self.backend = backend or CodeagentBackend()
        self.capacity = capacity or CapacityService(config, store, self.backend)
        self.lifecycle = lifecycle or ExecutionLifecycleService(store)
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

    def dispatch_execution(self, request: ExecutionRequest) -> ExecutionLaunchResult:
        """Dispatch an execution request.

        Simple dispatch model:
        1. Check for existing live session -> skip duplicate
        2. Check capacity -> skip if full
        3. Launch execution
        4. Record lifecycle event

        No in-flight or launching state tracking. True deduplication
        is based on live tmux session existence only.
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

        # 1. Check for existing truly live session (starting or running with live tmux)
        # to prevent duplicate launches if multiple dispatchers fire concurrently.
        if request.target_branch and not is_async_child_sync:
            live_sessions = self.registry.get_truly_live_sessions_for_target(
                role=request.role,
                branch=request.target_branch,
                target_id=str(request.target_id),
            )
            if live_sessions:
                logger.bind(
                    domain="execution_coordinator",
                    role=request.role,
                    target_id=request.target_id,
                    branch=request.target_branch,
                ).info(f"Already running for {request.role}, skipping duplicate")
                return ExecutionLaunchResult(
                    launched=False,
                    skipped=True,
                    reason=f"Execution already running for {request.role}",
                    reason_code="already_running",
                )

        # 2. Check capacity
        # Async child sync: outer wrapper already reserved capacity and registered
        # the runtime_session; child must not re-check or it double-counts itself.
        if not is_async_child_sync:
            if not self.capacity.can_dispatch(request.role):
                return ExecutionLaunchResult(
                    launched=False,
                    reason=f"Capacity full for {request.role}",
                    reason_code="capacity_full",
                )

        try:
            # 3. Launch
            cwd_path = self._resolve_cwd(request)
            env = request.env or dict(os.environ)

            # Launch async
            if request.mode == "async":
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

                refs = dict(request.refs)
                refs["tmux_session"] = tmux_session
                refs["log_path"] = log_path

                # 4. Record started (which handles session registry)
                # Type ignore because ExecutionRole is a Literal constraint
                self.lifecycle.record_started(
                    role=request.role,  # type: ignore[arg-type]
                    target=request.target_branch,
                    actor=request.actor,
                    refs=refs,
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

                task = request.refs.get("task")

                # 5. Record started
                # For async child sync, the outer wrapper already registered
                # the runtime_session, so the child should not create a duplicate.
                if not is_async_child_sync:
                    self.lifecycle.record_started(
                        role=request.role,  # type: ignore[arg-type]
                        target=request.target_branch,
                        actor=request.actor,
                        refs=request.refs,
                    )

                logger.bind(
                    domain="execution_coordinator",
                    role=request.role,
                    target_id=request.target_id,
                ).info(f"Execution started for {request.role} (sync)")

                # Execute sync
                result = self.backend.run(
                    prompt=request.prompt,
                    options=request.options,
                    task=task,
                    dry_run=request.dry_run,
                    session_id=request.refs.get("session_id"),
                    cwd=cwd_path,
                )

                if result.is_success():
                    self.lifecycle.record_completed(
                        role=request.role,  # type: ignore[arg-type]
                        target=request.target_branch,
                        actor=request.actor,
                        detail=f"Execution completed for {request.role}",
                        refs=request.refs,
                    )
                    logger.bind(
                        domain="execution_coordinator",
                        role=request.role,
                        target_id=request.target_id,
                    ).success(f"Execution completed for {request.role} (sync)")

                    return ExecutionLaunchResult(
                        launched=True,
                        stdout=result.stdout,  # Pass stdout for sync mode
                    )
                else:
                    error_msg = getattr(result, "stderr", "") or "Execution failed"
                    self.lifecycle.record_failed(
                        role=request.role,  # type: ignore[arg-type]
                        target=request.target_branch,
                        actor=request.actor,
                        error=error_msg,
                        refs=request.refs,
                    )
                    logger.bind(
                        domain="execution_coordinator",
                        role=request.role,
                        target_id=request.target_id,
                    ).warning(
                        f"Execution failed for {request.role} (sync): {error_msg}"
                    )

                    return ExecutionLaunchResult(
                        launched=False,
                        reason=error_msg,
                        reason_code="launch_failed",
                    )
            else:
                raise ValueError(f"Unknown mode: {request.mode}")

        except Exception as exc:
            logger.bind(
                domain="execution_coordinator",
                role=request.role,
                target_id=request.target_id,
            ).error(f"Execution launch failed: {exc}")

            self.lifecycle.record_failed(
                role=request.role,  # type: ignore[arg-type]
                target=request.target_branch,
                actor=request.actor,
                error=str(exc),
                refs=request.refs,
            )

            return ExecutionLaunchResult(
                launched=False,
                reason=str(exc),
                reason_code="launch_failed",
            )
