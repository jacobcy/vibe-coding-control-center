"""Job executor service for isolated async command execution.

This module provides a thin orchestration layer that accepts a JobEnvelope,
resolves the command adapter via the registry, dispatches through existing
execution paths (run_issue_role_async for issue roles, run_governance_sync
for governance), and returns a structured JobResult.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.execution.execution_lifecycle import ExecutionLifecycleService, ExecutionRole
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.execution.session_service import load_session_id
from vibe3.models.execution_request import ExecutionLaunchResult
from vibe3.models.job import CommandType, JobContext, JobEnvelope, JobResult
from vibe3.models.session_types import SessionRole

if TYPE_CHECKING:
    from vibe3.execution.command_adapter import CommandAdapterRegistry
    from vibe3.execution.role_interfaces import IssueRoleSyncSpec


# Mapping from CommandType to ExecutionRole for lifecycle events
COMMAND_TYPE_TO_EXECUTION_ROLE: dict[CommandType, ExecutionRole] = {
    CommandType.PLAN: "planner",
    CommandType.RUN: "executor",
    CommandType.REVIEW: "reviewer",
    CommandType.MANAGER: "manager",
    CommandType.GOVERNANCE_SCAN: "governance",
    CommandType.SUPERVISOR_APPLY: "supervisor",
}


class JobExecutor:
    """Executor service for isolated async command jobs.

    Accepts a JobEnvelope, resolves the adapter, dispatches through existing
    execution paths, captures lifecycle events, and returns a JobResult.

    This is a thin orchestration layer — it does not replace worktree/tmux/
    codeagent-wrapper launch semantics, but calls through to existing runners.
    """

    def __init__(self, registry: CommandAdapterRegistry, store: SQLiteClient) -> None:
        """Initialize executor with adapter registry and store.

        Args:
            registry: Command adapter registry for resolving handlers
            store: SQLite client for event persistence
        """
        self._registry = registry
        self._lifecycle = ExecutionLifecycleService(store)

    def execute(self, envelope: JobEnvelope) -> JobResult:
        """Execute a job from its envelope.

        Args:
            envelope: The job envelope containing all execution parameters

        Returns:
            Structured result of the execution

        Note:
            For async commands, status will be "launched" not "completed".
            The executor returns immediately after tmux launch.
        """
        started_at = datetime.now(tz=timezone.utc).isoformat()

        try:
            # Resolve adapter
            resolved = self._registry.resolve(envelope.command_type)
            adapter_path = resolved.entry.import_path
        except Exception as e:
            logger.error(f"Failed to resolve adapter for {envelope.command_type}: {e}")
            return JobResult(
                command_type=envelope.command_type,
                issue_number=envelope.issue_number,
                branch=envelope.branch,
                status="failed",
                started_at=started_at,
                error_message=f"Adapter resolution failed: {e}",
                error_code="ADAPTER_RESOLUTION_ERROR",
                source=envelope.source,
            )

        # Build context
        context = self._build_context(envelope)

        # Record lifecycle started event
        role = COMMAND_TYPE_TO_EXECUTION_ROLE.get(envelope.command_type)
        if role is None:
            logger.error(f"No execution role mapping for {envelope.command_type}")
            return JobResult(
                command_type=envelope.command_type,
                issue_number=envelope.issue_number,
                branch=envelope.branch,
                status="failed",
                started_at=started_at,
                error_message=f"No execution role mapping for {envelope.command_type}",
                error_code="ROLE_MAPPING_ERROR",
                source=envelope.source,
            )

        self._lifecycle.record_started(
            role=role,
            target=envelope.branch,
            actor=envelope.actor,
            session_id=context.session_id,
            refs=envelope.refs,
        )

        try:
            # Dispatch based on command type
            if envelope.command_type == CommandType.GOVERNANCE_SCAN:
                result = self._execute_governance(envelope)
            else:
                # Issue-scoped role (PLAN, RUN, REVIEW, MANAGER, SUPERVISOR)
                spec = resolved.callable
                if not hasattr(spec, "role_name"):
                    raise TypeError(
                        f"Resolved callable for {envelope.command_type} "
                        "is not an IssueRoleSyncSpec"
                    )
                result = self._execute_issue_role(envelope, spec)  # type: ignore[arg-type]

            # Map to JobResult
            job_result = self._map_launch_result(result, envelope, context)

            # Record lifecycle completion
            if job_result.status == "failed":
                self._lifecycle.record_failed(
                    role=role,
                    target=envelope.branch,
                    actor=envelope.actor,
                    error=job_result.error_message,
                    refs=envelope.refs,
                )
            elif job_result.status == "skipped":
                # Skipped is treated as a successful no-op
                self._lifecycle.record_completed(
                    role=role,
                    target=envelope.branch,
                    actor=envelope.actor,
                    detail="Execution skipped",
                    refs=envelope.refs,
                )
            else:
                # launched or completed
                self._lifecycle.record_completed(
                    role=role,
                    target=envelope.branch,
                    actor=envelope.actor,
                    detail=f"{envelope.command_type} {job_result.status}",
                    refs=envelope.refs,
                )

            # Fill in execution metadata
            job_result.started_at = started_at
            job_result.adapter_path = adapter_path

            return job_result

        except Exception as e:
            logger.exception(f"Job execution failed: {e}")

            # Record lifecycle failure
            self._lifecycle.record_failed(
                role=role,
                target=envelope.branch,
                actor=envelope.actor,
                error=str(e),
                refs=envelope.refs,
            )

            return JobResult(
                command_type=envelope.command_type,
                issue_number=envelope.issue_number,
                branch=envelope.branch,
                status="failed",
                started_at=started_at,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                source=envelope.source,
            )

    def _build_context(self, envelope: JobEnvelope) -> JobContext:
        """Build runtime context from envelope and environment.

        Args:
            envelope: The job envelope

        Returns:
            Populated CommandContext with runtime metadata
        """
        repo = resolve_orchestra_repo_root()

        # Try to get tmux session from environment
        tmux_session = os.environ.get("TMUX_PANE") or os.environ.get("TMUX")

        # Try to load session ID
        session_id = None
        try:
            # Map CommandType to SessionRole for load_session_id
            role_mapping: dict[CommandType, SessionRole] = {
                CommandType.PLAN: "planner",
                CommandType.RUN: "executor",
                CommandType.REVIEW: "reviewer",
                CommandType.MANAGER: "manager",
                CommandType.SUPERVISOR_APPLY: "supervisor",
                CommandType.GOVERNANCE_SCAN: "governance",
            }
            session_role = role_mapping.get(envelope.command_type)
            if session_role:
                session_id = load_session_id(session_role, envelope.branch)
        except Exception:
            # Session ID may not exist for all commands
            pass

        # Derive log path from execution naming convention
        # Note: This will be overwritten by actual launch result if available
        log_path = None
        if session_id:
            log_path = (
                f"logs/{envelope.command_type.value}-"
                f"{envelope.issue_number}-{session_id}.log"
            )

        return JobContext(
            issue_number=envelope.issue_number,
            branch=envelope.branch,
            tmux_session=tmux_session,
            session_id=session_id,
            log_path=log_path,
            worktree_path=(repo.worktree if hasattr(repo, "worktree") else None),
            cwd=os.getcwd(),
            repo_path=(
                repo.repo if hasattr(repo, "repo") else str(repo) if repo else None
            ),
            mode="async",  # Default to async mode
        )

    def _execute_issue_role(
        self, envelope: JobEnvelope, spec: IssueRoleSyncSpec
    ) -> ExecutionLaunchResult:
        """Execute an issue-scoped role via run_issue_role_async.

        Args:
            envelope: The job envelope
            spec: The role sync spec

        Returns:
            Execution launch result from the coordinator

        Note:
            This uses dry_run=False and provides None for optional CLI overrides.
            The spec handles default resolution.
        """
        # Import coordinator to get result directly
        from vibe3.agents import CodeagentBackend
        from vibe3.config import (
            load_orchestra_config,
        )
        from vibe3.execution.coordinator import ExecutionCoordinator
        from vibe3.services import load_issue_info

        repo = resolve_orchestra_repo_root()
        config = load_orchestra_config(target_repo=repo)
        issue = load_issue_info(envelope.issue_number, config=config)

        store = SQLiteClient()
        backend_instance = CodeagentBackend()
        coordinator = ExecutionCoordinator(config, store, backend_instance)

        # Build async request
        actor = envelope.actor
        request = spec.build_async_request(config, issue, actor, envelope.branch)
        if request is None:
            return ExecutionLaunchResult(
                launched=False,
                skipped=False,
                reason="Failed to build async request",
                reason_code="REQUEST_BUILD_ERROR",
            )

        # Dispatch execution
        try:
            result = coordinator.dispatch_execution(request)
            return result
        except Exception as e:
            logger.exception(f"Failed to dispatch {envelope.command_type}: {e}")
            return ExecutionLaunchResult(
                launched=False,
                skipped=False,
                reason=str(e),
                reason_code="DISPATCH_ERROR",
            )

    def _execute_governance(self, envelope: JobEnvelope) -> ExecutionLaunchResult:
        """Execute governance role.

        Args:
            envelope: The job envelope

        Returns:
            Execution launch result

        Note:
            Governance uses run_governance_sync with injected functions.
            For MVP, this is stubbed as governance requires different dispatch path.
        """
        # TODO: Implement governance execution path
        # Governance requires run_governance_sync with injected GovernanceFunctions
        # For now, return a placeholder result
        logger.warning(
            "Governance execution not yet implemented - returning skipped result"
        )
        return ExecutionLaunchResult(
            launched=False,
            skipped=True,
            reason="Governance execution not implemented in MVP",
            reason_code="NOT_IMPLEMENTED",
        )

    def _map_launch_result(
        self,
        result: ExecutionLaunchResult,
        envelope: JobEnvelope,
        context: JobContext,
    ) -> JobResult:
        """Map ExecutionLaunchResult to CommandResult.

        Args:
            result: The launch result from execution
            envelope: Original job envelope
            context: Runtime context

        Returns:
            Structured JobResult
        """
        # Determine status
        if result.skipped:
            status: Literal["launched", "completed", "failed", "skipped", "aborted"] = (
                "skipped"
            )
        elif result.launched:
            status = "launched"
        else:
            status = "failed"

        # Build updated context with metadata from launch result
        # Note: JobContext is frozen, so we create a new instance
        updated_context = JobContext(
            issue_number=context.issue_number,
            branch=context.branch,
            tmux_session=result.tmux_session or context.tmux_session,
            session_id=result.session_id or context.session_id,
            log_path=result.log_path or context.log_path,
            worktree_path=context.worktree_path,
            cwd=context.cwd,
            repo_path=context.repo_path,
            mode=context.mode,
        )

        # Build result with updated context
        job_result = JobResult(
            command_type=envelope.command_type,
            issue_number=envelope.issue_number,
            branch=envelope.branch,
            status=status,
            context=updated_context,
            source=envelope.source,
        )

        # Copy error information for failed and skipped
        if not result.launched:
            job_result.error_message = result.reason
            job_result.error_code = result.reason_code

        # Copy stdout for sync mode
        if result.stdout:
            job_result.payload_summary = {"stdout": result.stdout[:1000]}  # Truncate

        return job_result
