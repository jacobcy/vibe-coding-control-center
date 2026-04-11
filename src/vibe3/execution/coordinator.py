"""Unified execution coordinator."""

import os
from pathlib import Path
from typing import Optional

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.environment.worktree import WorktreeManager
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest
from vibe3.execution.execution_lifecycle import ExecutionLifecycleService
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.capacity_service import CapacityService


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

        repo_path = Path(request.repo_path) if request.repo_path else Path.cwd()
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
        """Dispatch an execution request."""
        logger.bind(
            domain="execution_coordinator",
            role=request.role,
            target_id=request.target_id,
            target_branch=request.target_branch,
        ).info(f"Received execution request for {request.role}")

        # 1. Check capacity
        if not self.capacity.can_dispatch(request.role, request.target_id):
            return ExecutionLaunchResult(
                launched=False,
                reason=f"Capacity full for {request.role}",
                reason_code="capacity_full",
            )

        # 2. Mark in-flight
        self.capacity.mark_in_flight(request.role, request.target_id)

        try:
            # 4. Launch
            cwd_path = self._resolve_cwd(request)
            env = request.env or dict(os.environ)

            # Ensure we launch async
            if request.mode == "async":
                if request.cmd:
                    handle = self.backend.start_async_command(
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

                # 5. Record started (which handles session registry)
                # Type ignore because ExecutionRole is a Literal constraint
                self.lifecycle.record_started(
                    role=request.role,  # type: ignore
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
                self.lifecycle.record_started(
                    role=request.role,  # type: ignore
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
                try:
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
                            role=request.role,  # type: ignore
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

                        return ExecutionLaunchResult(launched=True)
                    else:
                        error_msg = getattr(result, "stderr", "") or "Execution failed"
                        self.lifecycle.record_failed(
                            role=request.role,  # type: ignore
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
                except Exception as run_exc:
                    self.lifecycle.record_failed(
                        role=request.role,  # type: ignore
                        target=request.target_branch,
                        actor=request.actor,
                        error=str(run_exc),
                        refs=request.refs,
                    )
                    logger.bind(
                        domain="execution_coordinator",
                        role=request.role,
                        target_id=request.target_id,
                    ).exception(f"Execution threw for {request.role} (sync): {run_exc}")

                    return ExecutionLaunchResult(
                        launched=False,
                        reason=str(run_exc),
                        reason_code="launch_failed",
                    )
            else:
                raise ValueError(f"Unknown mode: {request.mode}")

        except Exception as exc:
            logger.bind(
                domain="execution_coordinator",
                role=request.role,
                target_id=request.target_id,
            ).exception(f"Execution launch failed: {exc}")

            self.lifecycle.record_failed(
                role=request.role,  # type: ignore
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
        finally:
            # 6. Prune in-flight
            self.capacity.prune_in_flight(request.role, {request.target_id})
