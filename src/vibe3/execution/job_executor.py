"""Job executor service for isolated async command execution.

This module provides a thin orchestration layer that accepts a JobEnvelope,
resolves the command adapter via the registry, dispatches through
ExecutionCoordinator (sync or async mode), and returns a structured JobResult.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
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
from vibe3.observability import logs_root
from vibe3.utils import compute_hash_from_loader

if TYPE_CHECKING:
    from vibe3.execution.command_adapter import CommandAdapterRegistry, ResolvedAdapter
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
        self._store = store

    def _resolve_coordinator(self, config: object) -> ExecutionCoordinator:
        """Resolve or create an ExecutionCoordinator.

        Uses the injected coordinator when available, otherwise creates a
        new one per invocation (original behavior).

        Args:
            config: Orchestra configuration

        Returns:
            ExecutionCoordinator instance
        """
        if self._coordinator is not None:
            return self._coordinator

        from vibe3.agents import CodeagentBackend
        from vibe3.execution.coordinator import ExecutionCoordinator

        store = SQLiteClient()
        backend_instance = CodeagentBackend()
        return ExecutionCoordinator(config, store, backend_instance)  # type: ignore[arg-type]

    def execute(self, envelope: JobEnvelope) -> JobResult:
        """Execute a job from its envelope.

        Manages actor lifecycle (create → launch → complete/fail/die) as a
        lightweight supervision wrapper around the existing execution path.
        Actor state is tracked in-memory and written to event_log.

        Args:
            envelope: The job envelope containing all execution parameters

        Returns:
            Structured result of the execution

        Note:
            For async commands, status will be "launched" not "completed".
            The executor returns immediately after tmux launch.
        """
        from vibe3.execution.actor import JobType, get_actor_registry

        started_at = datetime.now(tz=timezone.utc).isoformat()

        # Map CommandType to actor JobType
        _command_to_job_type: dict[CommandType, JobType] = {
            CommandType.GOVERNANCE_SCAN: JobType.GOVERNANCE,
        }
        job_type = _command_to_job_type.get(envelope.command_type, JobType.DISPATCH)

        # Create actor for supervision tracking
        registry = get_actor_registry()
        actor_obj = registry.create_actor(
            job_type=job_type,
            issue_number=envelope.issue_number,
            branch=envelope.branch,
            store=self._store,
        )

        try:
            # Resolve adapter
            resolved = self._registry.resolve(envelope.command_type)
            adapter_path = resolved.entry.import_path
        except Exception as e:
            # Pre-launch failure: actor still QUEUED, just clean up
            registry.remove_actor(actor_obj.actor_id)
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

        # Compute version hashes (non-blocking: failure returns None)
        try:
            adapter_hash = self._compute_adapter_hash(resolved)
        except Exception:
            adapter_hash = None

        from vibe3.clients import resolve_runtime_asset
        from vibe3.services.shared import material_loader, policy_loader

        materials_dir = resolve_runtime_asset("supervisor/governance")
        material_hash = (
            compute_hash_from_loader(material_loader, materials_dir)
            if materials_dir.exists()
            else None
        )
        policies_dir = resolve_runtime_asset(".agent/governance/policies")
        policy_hash = (
            compute_hash_from_loader(policy_loader, policies_dir)
            if policies_dir.exists()
            else None
        )

        # Record lifecycle started event
        role = COMMAND_TYPE_TO_EXECUTION_ROLE.get(envelope.command_type)
        if role is None:
            # Pre-launch failure: actor still QUEUED, just clean up
            registry.remove_actor(actor_obj.actor_id)
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

        # Record actor launch and lifecycle started
        actor_obj.record_launch()

        # Prepare version refs for lifecycle events
        version_refs: dict[str, str] = {
            "adapter_hash": adapter_hash or "",
            "policy_hash": policy_hash or "",
            "material_hash": material_hash or "",
        }

        self._lifecycle.record_started(
            role=role,
            target=envelope.branch,
            actor=envelope.actor,
            session_id=context.session_id,
            refs={
                **(envelope.refs or {}),
                "actor_id": actor_obj.actor_id,
                **version_refs,
            },
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
                # Route based on mode
                if envelope.mode == "sync":
                    result = self._execute_issue_role_sync(envelope, spec)  # type: ignore[arg-type]
                else:
                    result = self._execute_issue_role(envelope, spec)  # type: ignore[arg-type]

            # Map to JobResult
            job_result = self._map_launch_result(result, envelope, context)

            # Record lifecycle completion and actor terminal state
            if job_result.status == "failed":
                actor_obj.record_failure(
                    error=job_result.error_message or "dispatch failed"
                )
                self._lifecycle.record_failed(
                    role=role,
                    target=envelope.branch,
                    actor=envelope.actor,
                    error=job_result.error_message,
                    refs={**(envelope.refs or {}), **version_refs},
                )
            elif job_result.status == "skipped":
                actor_obj.record_completion(detail=f"{envelope.command_type} skipped")
                self._lifecycle.record_completed(
                    role=role,
                    target=envelope.branch,
                    actor=envelope.actor,
                    detail="Execution skipped",
                    refs={**(envelope.refs or {}), **version_refs},
                )
            else:
                # launched or completed
                actor_obj.record_completion(
                    detail=f"{envelope.command_type} {job_result.status}"
                )
                self._lifecycle.record_completed(
                    role=role,
                    target=envelope.branch,
                    actor=envelope.actor,
                    detail=f"{envelope.command_type} {job_result.status}",
                    refs={**(envelope.refs or {}), **version_refs},
                )

            # Fill in execution metadata
            job_result.started_at = started_at
            job_result.adapter_path = adapter_path
            job_result.policy_hash = policy_hash
            job_result.material_hash = material_hash
            job_result.adapter_hash = adapter_hash
            job_result.actor_id = actor_obj.actor_id

            # Actor stays in registry for TTL-based monitoring;
            # cleanup_expired() will remove it after the TTL window.
            return job_result

        except Exception as e:
            from vibe3.services.shared import log_dispatch_error

            log_dispatch_error("Job execution failed", e)

            # Record actor failure and lifecycle failure
            actor_obj.record_failure(error=str(e))
            self._lifecycle.record_failed(
                role=role,
                target=envelope.branch,
                actor=envelope.actor,
                error=str(e),
                refs={**(envelope.refs or {}), **version_refs},
            )

            # Actor stays in registry for TTL-based monitoring
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
            mode=envelope.mode,
        )

    def _execute_issue_role(
        self, envelope: JobEnvelope, spec: IssueRoleSyncSpec
    ) -> ExecutionLaunchResult:
        """Execute an issue-scoped role via ExecutionCoordinator (async mode).

        Uses the injected coordinator when available, otherwise creates one
        per invocation (original behavior).

        Args:
            envelope: The job envelope
            spec: The role sync spec

        Returns:
            Execution launch result from the coordinator
        """
        from vibe3.config import load_orchestra_config

        repo = resolve_orchestra_repo_root()
        config = load_orchestra_config(target_repo=repo)
        coordinator = self._resolve_coordinator(config)

        return self._dispatch_via_coordinator(coordinator, envelope, spec)

    def _execute_issue_role_sync(
        self, envelope: JobEnvelope, spec: IssueRoleSyncSpec
    ) -> ExecutionLaunchResult:
        """Execute an issue-scoped role via ExecutionCoordinator (sync mode).

        Uses build_sync_request instead of build_async_request, supporting
        flow_state, session_id, dry_run, and show_prompt parameters.

        Args:
            envelope: The job envelope
            spec: The role sync spec

        Returns:
            Execution launch result from the coordinator
        """
        from vibe3.config import load_orchestra_config
        from vibe3.services.issue import load_issue_info

        repo = resolve_orchestra_repo_root()
        config = load_orchestra_config(target_repo=repo)
        issue = load_issue_info(envelope.issue_number, config=config)
        coordinator = self._resolve_coordinator(config)

        # Extract sync-specific parameters from envelope
        flow_state = envelope.refs.get("flow_state")
        session_id = envelope.refs.get("session_id")
        dry_run = envelope.refs.get("dry_run", "false").lower() == "true"
        show_prompt = envelope.refs.get("show_prompt", "false").lower() == "true"

        # Build sync request
        # Note: options and actor are derived from config and envelope
        from vibe3.execution.issue_role_sync_runner import format_agent_actor

        cli_overrides = envelope.cli_overrides or {}
        options = spec.resolve_options(config, cli_overrides)
        actor = format_agent_actor(options)

        sync_request = spec.build_sync_request(
            config,
            issue,
            envelope.branch,
            flow_state,
            session_id,
            options,
            actor,
            dry_run,
            show_prompt,
        )

        if sync_request is None:
            return ExecutionLaunchResult(
                launched=False,
                skipped=False,
                reason="Failed to build sync request",
                reason_code="REQUEST_BUILD_ERROR",
            )

        try:
            return coordinator.dispatch_execution(sync_request)
        except Exception as e:
            logger.exception(f"Failed to dispatch {envelope.command_type} (sync): {e}")
            return ExecutionLaunchResult(
                launched=False,
                skipped=False,
                reason=str(e),
                reason_code="DISPATCH_ERROR",
            )

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
        from vibe3.services.issue import load_issue_info

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
            Governance dispatch builds an ExecutionRequest that calls the CLI
            self-invocation pattern, similar to governance_scan.py and
            governance_sync_runner.py.
        """
        from vibe3.config import GOVERNANCE_GATE_CONFIG, load_orchestra_config
        from vibe3.execution.issue_role_support import resolve_async_cli_project_root
        from vibe3.models import ExecutionRequest

        repo = resolve_orchestra_repo_root()
        config = load_orchestra_config(target_repo=repo)

        # Resolve material: use override if provided, otherwise rotate from catalog
        from vibe3.prompts import (
            build_governance_execution_name,
            resolve_governance_material,
        )

        resolved_material = (
            envelope.governance_material_override
            if envelope.governance_material_override
            else resolve_governance_material(
                config, envelope.governance_execution_count
            )
        )
        execution_name = build_governance_execution_name(
            envelope.governance_tick_count, material=resolved_material
        )

        command_root = resolve_async_cli_project_root(repo)
        cmd = [
            "uv",
            "run",
            "--project",
            str(command_root),
            "python",
            "-I",
            str((command_root / "src" / "vibe3" / "cli.py").resolve()),
            "internal",
            "governance",
            str(envelope.governance_tick_count),
            str(envelope.governance_execution_count),
        ]

        # Add material override if provided
        if envelope.governance_material_override:
            cmd.extend(["--material", envelope.governance_material_override])

        # Build environment
        env = dict(os.environ)
        env.pop("VIBE3_ASYNC_CLI_PROJECT_ROOT", None)
        env["VIBE3_ASYNC_CHILD"] = "1"
        env["VIBE3_ORCHESTRA_EVENT_LOG"] = "1"
        # Force logs to be written to the target project, not the vibe repo
        env["VIBE3_ASYNC_LOG_DIR"] = str(logs_root())

        # Build execution request
        request = ExecutionRequest(
            role="governance",
            target_branch="governance",
            target_id=1,
            execution_name=execution_name,
            cmd=cmd,
            repo_path=str(repo),
            env=env,
            refs={
                "tick": str(envelope.governance_tick_count),
                "execution_count": str(envelope.governance_execution_count),
            },
            actor=envelope.actor,
            mode="async",
            worktree_requirement=GOVERNANCE_GATE_CONFIG,
        )

        coordinator = self._resolve_coordinator(config)

        try:
            return coordinator.dispatch_execution(request)
        except Exception as e:
            logger.exception(f"Failed to dispatch governance: {e}")
            return ExecutionLaunchResult(
                launched=False,
                skipped=False,
                reason=str(e),
                reason_code="DISPATCH_ERROR",
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

    def _compute_adapter_hash(self, resolved: "ResolvedAdapter") -> str | None:
        """Compute SHA-256 hash of the resolved adapter's source file.

        Args:
            resolved: The resolved adapter object from registry.resolve()

        Returns:
            First 16 hex chars of SHA-256 hash, or None if module file cannot be found
        """
        import importlib

        try:
            if not hasattr(resolved, "module_name"):
                return None

            module = importlib.import_module(resolved.module_name)
            if not hasattr(module, "__file__") or module.__file__ is None:
                return None

            content = Path(module.__file__).read_text(encoding="utf-8")
            return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        except Exception as e:
            logger.warning(f"Failed to compute adapter hash: {e}")
            return None
