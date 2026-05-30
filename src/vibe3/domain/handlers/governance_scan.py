"""Governance scan domain event handler.

Subscribes to GovernanceScanStarted and dispatches the governance agent
via CLI self-invocation (internal governance) to ensure ErrorTrackingService
captures API errors in the sync chain.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.store_context import get_store
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.domain.handler_registry import register_handler
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest
from vibe3.execution.role_contracts import GOVERNANCE_GATE_CONFIG
from vibe3.services.error_helpers import record_dispatch_failure_if_unexpected

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.config.orchestra_config import OrchestraConfig
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.services.orchestra_status_service import OrchestraStatusService


@dataclass(frozen=True)
class GovernanceScanDependencies:
    """Pre-built service bundle for governance scan handler."""

    registry: SessionRegistryService
    status_service: OrchestraStatusService

    @staticmethod
    def build(
        config: OrchestraConfig, store: SQLiteClient
    ) -> GovernanceScanDependencies:
        """Build dependencies with required services.

        Args:
            config: OrchestraConfig instance
            store: SQLiteClient instance from get_store()

        Returns:
            GovernanceScanDependencies with registry and status_service
        """
        from vibe3.agents.backends.codeagent import CodeagentBackend
        from vibe3.domain import FlowManager
        from vibe3.environment.session_registry import SessionRegistryService
        from vibe3.services.orchestra_status_service import OrchestraStatusService

        backend = CodeagentBackend()
        registry = SessionRegistryService(store, backend)
        flow_manager = FlowManager(config)
        status_service = OrchestraStatusService(config, orchestrator=flow_manager)
        return GovernanceScanDependencies(
            registry=registry, status_service=status_service
        )


@register_handler("GovernanceScanStarted")
def handle_governance_scan_started(
    event: GovernanceScanStarted, /, deps: GovernanceScanDependencies | None = None
) -> None:
    """Dispatch governance scan via CLI self-invocation."""
    from vibe3.execution.issue_role_support import (
        resolve_async_cli_project_root,
        resolve_orchestra_repo_root,
    )
    from vibe3.orchestra.logging import append_governance_event
    from vibe3.roles.governance import build_governance_execution_name

    config = load_orchestra_config()

    with get_store() as store:
        resolved = deps or GovernanceScanDependencies.build(config, store)
        resolved.registry.mark_governance_sessions_done_when_tmux_gone()
        live_governance = resolved.registry.list_live_governance_sessions()
        if len(live_governance) >= config.governance_max_concurrent:
            session_names = ", ".join(
                str(session.get("tmux_session") or session.get("session_name") or "?")
                for session in live_governance[:3]
            )
            skip_result = ExecutionLaunchResult(
                launched=False,
                skipped=True,
                reason=(
                    "governance already running"
                    if not session_names
                    else f"governance already running ({session_names})"
                ),
                reason_code="governance_already_running",
            )
            append_governance_event(
                f"governance dispatch skipped: tick={event.tick_count} "
                f"reason={skip_result.reason}"
            )
            logger.bind(
                domain="governance_handler",
                tick=event.tick_count,
                live_governance=len(live_governance),
                governance_max=config.governance_max_concurrent,
            ).info(
                "Skipping governance scan because another governance session is live"
            )
            return

    snapshot = resolved.status_service.snapshot()

    # Resolve repo root once (used for circuit breaker skip log and CLI command)
    root = resolve_orchestra_repo_root()

    # Check circuit breaker before dispatching
    if snapshot.circuit_breaker_state == "open":
        append_governance_event("skipped: circuit breaker OPEN", repo_root=root)
        return

    execution_name = build_governance_execution_name(event.tick_count)

    # Build CLI self-invocation request (cmd field, no prompt)
    # This ensures the tmux wrapper calls 'internal governance <tick>'
    # which enters governance_sync_runner with ErrorTrackingService
    command_root = resolve_async_cli_project_root(root)
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
        str(event.tick_count),
    ]

    env = dict(os.environ)
    env["VIBE3_ASYNC_CHILD"] = "1"
    # Ensure governance child process can write to events.log
    env["VIBE3_ORCHESTRA_EVENT_LOG"] = "1"

    request = ExecutionRequest(
        role="governance",
        target_branch="governance",
        target_id=1,
        execution_name=execution_name,
        cmd=cmd,
        repo_path=str(root),
        env=env,
        refs={"tick": str(event.tick_count)},
        actor="orchestra:governance",
        mode="async",
        worktree_requirement=GOVERNANCE_GATE_CONFIG,
    )

    with get_store() as store:
        from vibe3.execution.coordinator import ExecutionCoordinator

        coordinator = ExecutionCoordinator(config, store)

        try:
            result = coordinator.dispatch_execution(request)
            record_dispatch_failure_if_unexpected(
                result=result,
                role="governance",
                issue_number=None,
                branch="governance",
                tick_id=event.tick_count,
                dispatch_source="automatic",
            )
        except Exception as exc:
            record_dispatch_failure_if_unexpected(
                role="governance",
                issue_number=None,
                branch="governance",
                exception=exc,
                tick_id=event.tick_count,
                dispatch_source="automatic",
            )
            logger.bind(
                domain="governance_handler",
                tick=event.tick_count,
            ).exception(f"Governance scan dispatch failed: {exc}")
            return

    if result and result.launched:
        append_governance_event(
            f"governance agent launched: tick={event.tick_count} "
            f"session={result.tmux_session}",
        )
    elif result:
        append_governance_event(
            f"governance dispatch skipped: tick={event.tick_count} "
            f"reason={result.reason}",
        )
