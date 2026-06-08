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
from vibe3.models import (
    CommandType,
    ExecutionLaunchResult,
    JobContext,
    JobEnvelope,
    JobResult,
)

if TYPE_CHECKING:
    from vibe3.execution.command_adapter import CommandAdapterRegistry
    from vibe3.execution.coordinator import ExecutionCoordinator
    from vibe3.execution.role_interfaces import IssueRoleSyncSpec

# Mapping from CommandType to ExecutionRole for lifecycle events.
# Also used for SessionRole lookup since both share the same string values.
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

    def __init__(
        self,
        registry: CommandAdapterRegistry,
        store: SQLiteClient,
        coordinator: ExecutionCoordinator | None = None,
    ) -> None:
        """Initialize executor with adapter registry and store.

        Args:
            registry: Command adapter registry for resolving handlers
            store: SQLite client for event persistence
            coordinator: Optional pre-built ExecutionCoordinator for dispatch.
                When provided, _execute_issue_role uses it instead of creating
                a new one per invocation. When None, a coordinator is created
                on each call (preserving the original behavior).
        """
        self._registry = registry
        self._lifecycle = ExecutionLifecycleService(store)
        self._coordinator = coordinator

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

        # Build context (no premature session ID loading —
        # session metadata comes from ExecutionLaunchResult after dispatch)
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

        Does not attempt to load session IDs — session metadata is populated
        from ExecutionLaunchResult after dispatch, avoiding race conditions
        with concurrent dispatches for the same branch/role.

        Args:
            envelope: The job envelope

        Returns:
            Populated JobContext with runtime metadata
        """
        repo = resolve_orchestra_repo_root()

        return JobContext(
            issue_number=envelope.issue_number,
            branch=envelope.branch,
            tmux_session=os.environ.get("TMUX_PANE") or os.environ.get("TMUX"),
            worktree_path=(repo.worktree if hasattr(repo, "worktree") else None),
            cwd=os.getcwd(),
            repo_path=(
                repo.repo if hasattr(repo, "repo") else str(repo) if repo else None
            ),
            mode="async",
        )

    def _execute_issue_role(
        self, envelope: JobEnvelope, spec: IssueRoleSyncSpec
    ) -> ExecutionLaunchResult:
        """Execute an issue-scoped role via ExecutionCoordinator.

        Uses the injected coordinator when available, otherwise creates one
        per invocation (original behavior).

        Args:
            envelope: The job envelope
            spec: The role sync spec

        Returns:
            Execution launch result from the coordinator
        """
        if self._coordinator is not None:
            return self._dispatch_via_coordinator(self._coordinator, envelope, spec)

        # Fallback: create coordinator per invocation (original behavior)
        from vibe3.agents import CodeagentBackend
        from vibe3.config import load_orchestra_config
        from vibe3.execution.coordinator import ExecutionCoordinator

        repo = resolve_orchestra_repo_root()
        config = load_orchestra_config(target_repo=repo)

        store = SQLiteClient()
        backend_instance = CodeagentBackend()
        coordinator = ExecutionCoordinator(config, store, backend_instance)

        return self._dispatch_via_coordinator(coordinator, envelope, spec)

    def _dispatch_via_coordinator(
        self,
        coordinator: ExecutionCoordinator,
        envelope: JobEnvelope,
        spec: IssueRoleSyncSpec,
    ) -> ExecutionLaunchResult:
        """Build async request and dispatch through coordinator.

        Args:
            coordinator: Execution coordinator to use
            envelope: The job envelope
            spec: The role sync spec

        Returns:
            Execution launch result
        """
        from vibe3.config import load_orchestra_config
        from vibe3.services import load_issue_info

        repo = resolve_orchestra_repo_root()
        config = load_orchestra_config(target_repo=repo)
        issue = load_issue_info(envelope.issue_number, config=config)

        request = spec.build_async_request(
            config, issue, envelope.actor, envelope.branch
        )
        if request is None:
            return ExecutionLaunchResult(
                launched=False,
                skipped=False,
                reason="Failed to build async request",
                reason_code="REQUEST_BUILD_ERROR",
            )

        try:
            return coordinator.dispatch_execution(request)
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
