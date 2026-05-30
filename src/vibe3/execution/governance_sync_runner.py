"""Sync execution runner for governance scan.

Provides sync execution with ErrorTrackingService integration,
ensuring API errors are captured for FailedGate threshold checking.
"""

from __future__ import annotations

import os
from typing import Callable

from loguru import logger
from typer import echo

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.store_context import get_store
from vibe3.config import load_orchestra_config
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest
from vibe3.execution.role_contracts import GOVERNANCE_GATE_CONFIG
from vibe3.execution.role_interfaces import GovernanceEventLogger, GovernanceFunctions
from vibe3.services.error_helpers import record_dispatch_failure_if_unexpected


def run_governance_sync(
    *,
    tick_count: int,
    material_override: str | None = None,
    dry_run: bool = False,
    show_prompt: bool = False,
    session_id: str | None = None,
    governance_fns: GovernanceFunctions | None = None,
    append_event: GovernanceEventLogger | None = None,
) -> None:
    """Run governance scan synchronously with error tracking.

    This function is called by `internal governance --no-async` CLI command.
    It rebuilds the runtime snapshot, renders the governance prompt,
    and executes through CodeagentBackend with ErrorTrackingService integration.

    Args:
        tick_count: Tick number for governance material rotation
        material_override: Optional governance role to override material rotation
        dry_run: If True, print command without executing
        show_prompt: If True, print prompt content in dry-run mode
        session_id: Optional session ID for resume
        governance_fns: Optional injected governance functions (for decoupling)
        append_event: Optional injected event logger (for decoupling)
    """
    # Default fallback via lazy import for backward compatibility
    if governance_fns is None:
        from vibe3.roles.governance_factory import build_default_governance_fns

        governance_fns = build_default_governance_fns()

    if append_event is None:
        from vibe3.orchestra.logging import append_governance_event as _ae

        append_event = _ae

    config = load_orchestra_config()
    from vibe3.domain import FlowManager
    from vibe3.services.orchestra_status_service import OrchestraStatusService

    flow_manager = FlowManager(config)
    status_service = OrchestraStatusService(config, orchestrator=flow_manager)
    snapshot = status_service.snapshot()

    # Resolve agent options
    options = governance_fns.resolve_options(config)

    # Build prompt via snapshot context and prompt assembler
    snapshot_context = governance_fns.build_snapshot_context(
        snapshot,
        config=config,
        tick_count=tick_count,
        material_override=material_override,
    )
    render_result = governance_fns.render_prompt(
        config,
        snapshot_context,
        tick_count=tick_count,
        material_override=material_override,
    )
    prompt_content = render_result.rendered_text

    if dry_run:
        material_info = f" material={material_override}" if material_override else ""
        echo(f"-> Governance dry-run: tick={tick_count}{material_info}")
        if show_prompt:
            echo("--- Prompt ---")
            echo(
                prompt_content[:2000] + "..."
                if len(prompt_content) > 2000
                else prompt_content
            )
        return

    material_info = f" material={material_override}" if material_override else ""
    echo(f"-> Executing governance tick={tick_count}{material_info}...")

    try:
        result = CodeagentBackend().run(
            prompt=prompt_content,
            options=options,
            task="governance scan",
            dry_run=False,
            session_id=session_id,
            cwd=None,  # Governance runs in current worktree
            role="governance",
            show_prompt=False,
        )

        # Log successful completion
        append_event(
            f"governance scan completed tick={tick_count} "
            f"exit_code={result.exit_code}"
        )
        logger.bind(domain="governance", tick=tick_count).success(
            f"Governance scan completed: {result.exit_code}"
        )

    except Exception as exc:
        # Error tracking: classify and record for FailedGate threshold
        from vibe3.exceptions.error_classification import classify_error_hybrid
        from vibe3.services.error_helpers import record_error

        error_code = classify_error_hybrid(exc)

        # Record error with tick_id (governance has no specific issue/branch)
        record_error(
            error_code=error_code,
            error_message=str(exc),
            tick_id=tick_count,
        )

        logger.bind(domain="governance", tick=tick_count).error(
            f"Governance scan failed: {error_code} - {exc}"
        )
        append_event(
            f"governance scan failed tick={tick_count} " f"error={error_code}: {exc}"
        )

        # Re-raise for CLI exit code handling
        raise


def run_governance_async(
    *,
    tick_count: int = 0,
    material_override: str | None = None,
    build_execution_name: Callable[[int], str] | None = None,
) -> None:
    """Run governance scan in background tmux session (async).

    Builds a CLI self-invocation ExecutionRequest and dispatches via
    ExecutionCoordinator, matching the plan/run/review async dispatch pattern.
    Checks for concurrent governance sessions and circuit breaker before dispatching.

    Args:
        tick_count: Tick number for governance material rotation
        material_override: Optional governance role to override material rotation
        build_execution_name: Optional injected execution name builder (for decoupling)
    """
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.coordinator import ExecutionCoordinator
    from vibe3.execution.issue_role_support import (
        resolve_async_cli_project_root,
        resolve_orchestra_repo_root,
    )

    # Default fallback via lazy import
    if build_execution_name is None:
        from vibe3.roles.governance import build_governance_execution_name as _ben

        build_execution_name = _ben

    from vibe3.domain import FlowManager
    from vibe3.orchestra.logging import append_governance_event
    from vibe3.services.orchestra_status_service import OrchestraStatusService

    config = load_orchestra_config()

    # Check for concurrent governance sessions (same dedup logic as orchestra handler)
    with get_store() as store:
        backend = CodeagentBackend()
        registry = SessionRegistryService(store, backend)
        registry.mark_governance_sessions_done_when_tmux_gone()
        live_governance = registry.list_live_governance_sessions()
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
                f"governance dispatch skipped: tick={tick_count} "
                f"reason={skip_result.reason}"
            )
            echo(skip_result.reason)
            return

    flow_manager = FlowManager(config)
    status_service = OrchestraStatusService(config, orchestrator=flow_manager)
    snapshot = status_service.snapshot()

    root = resolve_orchestra_repo_root()

    # Check circuit breaker before dispatching
    if snapshot.circuit_breaker_state == "open":
        append_governance_event("skipped: circuit breaker OPEN", repo_root=root)
        echo("Governance dispatch skipped: circuit breaker is OPEN")
        return

    execution_name = build_execution_name(tick_count)

    # Build CLI self-invocation command
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
        str(tick_count),
    ]
    if material_override:
        cmd.extend(["--material", material_override])

    env = dict(os.environ)
    env["VIBE3_ASYNC_CHILD"] = "1"
    env["VIBE3_ORCHESTRA_EVENT_LOG"] = "1"
    # Force logs to be written to the target project, not the vibe repo
    env["VIBE3_ASYNC_LOG_DIR"] = str(root / "temp" / "logs")

    request = ExecutionRequest(
        role="governance",
        target_branch="governance",
        target_id=1,
        execution_name=execution_name,
        cmd=cmd,
        repo_path=str(root),
        env=env,
        refs={"tick": str(tick_count)},
        actor="cli:governance",
        mode="async",
        worktree_requirement=GOVERNANCE_GATE_CONFIG,
    )

    with get_store() as store:
        backend = CodeagentBackend()
        coordinator = ExecutionCoordinator(config, store, backend)

        try:
            result = coordinator.dispatch_execution(request)
            record_dispatch_failure_if_unexpected(
                result=result,
                role="governance",
                issue_number=None,
                branch="governance",
                tick_id=tick_count,
            )
        except Exception as exc:
            record_dispatch_failure_if_unexpected(
                role="governance",
                issue_number=None,
                branch="governance",
                exception=exc,
                tick_id=tick_count,
            )
            logger.exception(f"Governance scan dispatch failed: {exc}")
            raise

    if result and result.launched:
        append_governance_event(
            f"governance agent launched: tick={tick_count} "
            f"session={result.tmux_session}",
        )
        log_info = f"Log: {result.log_path}" if result.log_path else ""
        message = f"Governance scan dispatched in tmux session: {result.tmux_session}"
        if log_info:
            message += f"\n{log_info}"
        echo(message)
    elif result:
        append_governance_event(
            f"governance dispatch skipped: tick={tick_count} "
            f"reason={result.reason}",
        )
        echo(f"Governance scan skipped: {result.reason}")
