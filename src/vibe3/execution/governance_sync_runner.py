"""Sync execution runner for governance scan.

Provides sync execution with ErrorTrackingService integration,
ensuring API errors are captured for FailedGate threshold checking.
"""

from __future__ import annotations

import os
from typing import Callable

from loguru import logger
from typer import echo

from vibe3.agents import CodeagentBackend, CodeagentResult
from vibe3.clients import get_store
from vibe3.config import (
    GOVERNANCE_GATE_CONFIG,
    load_orchestra_config,
)
from vibe3.execution.codeagent_support import resolve_display_agent_options
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.execution.role_interfaces import GovernanceEventLogger, GovernanceFunctions
from vibe3.models import ExecutionLaunchResult, ExecutionRequest
from vibe3.observability import write_prompt_provenance
from vibe3.prompts import PromptManifest, collect_dry_run_provenance
from vibe3.services.orchestra import record_dispatch_failure_if_unexpected
from vibe3.services.shared import log_dispatch_error


def run_governance_sync(
    *,
    tick_count: int,
    execution_count: int = 0,
    material_override: str | None = None,
    dry_run: bool = False,
    show_prompt: bool = False,
    session_id: str | None = None,
    governance_fns: GovernanceFunctions,
    append_event: GovernanceEventLogger,
) -> CodeagentResult | None:
    """Run governance scan synchronously with error tracking.

    This function is called by `internal governance --no-async` CLI command.
    It rebuilds the runtime snapshot, renders the governance prompt,
    and executes through CodeagentBackend with ErrorTrackingService integration.

    Args:
        tick_count: Tick number for governance material rotation
        execution_count: Independent counter for material rotation
            (resolves tick conflict)
        material_override: Optional governance role to override material rotation
        dry_run: If True, print command without executing
        show_prompt: If True, print prompt content in dry-run mode
        session_id: Optional session ID for resume
        governance_fns: Injected governance functions (required)
        append_event: Injected event logger (required)

    Returns:
        CodeagentResult in dry-run mode (for consistent display),
        None for real execution (caller handles display separately).
    """
    repo = resolve_orchestra_repo_root()
    config = load_orchestra_config(target_repo=repo)
    from vibe3.services.orchestra import OrchestraStatusService

    status_service = OrchestraStatusService.create(config)
    snapshot = status_service.snapshot()

    # Resolve agent options
    options = governance_fns.resolve_options(config)

    # Build prompt via snapshot context and prompt assembler
    snapshot_context = governance_fns.build_snapshot_context(
        snapshot,
        config=config,
        tick_count=tick_count,
        execution_count=execution_count,
        material_override=material_override,
    )
    render_result = governance_fns.render_prompt(
        config,
        snapshot_context,
        tick_count=tick_count,
        execution_count=execution_count,
        material_override=material_override,
    )
    prompt_content = render_result.rendered_text

    if dry_run:
        manifest = PromptManifest.load_for_prompts_path(None)
        recipe_def = manifest.recipe("governance.scan")
        variant_key = ""
        if recipe_def.variants:
            variant_key = "default"

        sections = ["governance.scan"]
        # template-based recipes have a single logical section
        dry_run_summary: dict[str, object] = {
            "prompt_mode": "scan",
            "context_mode": "tick",
            "sections": sections,
            "refs": {
                "role": "governance",
                "tick": str(tick_count),
            },
        }

        # Collect and write provenance
        provenance = collect_dry_run_provenance(
            manifest=manifest,
            recipe_key="governance.scan",
            variant_key=variant_key,
            rendered_text=prompt_content,
            variable_provenance=render_result.provenance,
            warnings=render_result.warnings,
        )
        provenance_path = write_prompt_provenance(
            provenance, role="governance", repo_root=repo
        )
        dry_run_summary["provenance_path"] = str(provenance_path)

        # Add section annotation for template-based prompt
        annotated_prompt = (
            f"<!-- section:governance.scan -->\n"
            f"{prompt_content}\n"
            f"<!-- /section:governance.scan -->"
        )

        # Route through CodeagentBackend for consistent dry-run display
        CodeagentBackend().run(
            prompt=annotated_prompt,
            options=options,
            task="governance scan",
            dry_run=True,
            show_prompt=show_prompt,
            role="governance",
            dry_run_summary=dry_run_summary,
        )

        # Return CodeagentResult for consistent display with plan/run/review
        effective = resolve_display_agent_options(options)
        return CodeagentResult(
            success=True,
            backend=effective.backend,
            model=effective.model,
        )

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
            f"governance scan completed tick={tick_count} exit_code={result.exit_code}"
        )
        logger.bind(domain="governance", tick=tick_count).success(
            f"Governance scan completed: {result.exit_code}"
        )

    except Exception as exc:
        # Error tracking: classify and record for FailedGate threshold
        from vibe3.exceptions import classify_error_hybrid
        from vibe3.services.orchestra import record_error

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
            f"governance scan failed tick={tick_count} error={error_code}: {exc}"
        )

        # Re-raise for CLI exit code handling
        raise

    return None


def run_governance_async(
    *,
    tick_count: int = 0,
    execution_count: int = 0,
    material_override: str | None = None,
    build_execution_name: Callable[[int, str | None], str],
) -> None:
    """Run governance scan in background tmux session (async).

    Builds a CLI self-invocation ExecutionRequest and dispatches via
    ExecutionCoordinator, matching the plan/run/review async dispatch pattern.
    Checks for concurrent governance sessions and circuit breaker before dispatching.

    Args:
        tick_count: Tick number for governance material rotation
        execution_count: Execution count for material rotation
        material_override: Optional governance role to override material rotation
        build_execution_name: Injected execution name builder
            (required, accepts tick and optional material)
    """
    from vibe3.environment import SessionRegistryService
    from vibe3.execution.coordinator import ExecutionCoordinator
    from vibe3.execution.issue_role_support import (
        resolve_async_cli_project_root,
        resolve_orchestra_repo_root,
    )
    from vibe3.observability import append_governance_event
    from vibe3.prompts import resolve_governance_material
    from vibe3.services.orchestra import OrchestraStatusService

    repo = resolve_orchestra_repo_root()
    config = load_orchestra_config(target_repo=repo)

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

    status_service = OrchestraStatusService.create(config)
    snapshot = status_service.snapshot()

    root = resolve_orchestra_repo_root()

    # Check circuit breaker before dispatching
    if snapshot.circuit_breaker_state == "open":
        append_governance_event("skipped: circuit breaker OPEN", repo_root=root)
        echo("Governance dispatch skipped: circuit breaker is OPEN")
        return

    # Resolve material: use override if provided, otherwise rotate from catalog
    resolved_material = (
        material_override
        if material_override
        else resolve_governance_material(config, execution_count)
    )
    execution_name = build_execution_name(tick_count, resolved_material)

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
            log_dispatch_error("Governance scan dispatch failed", exc)
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
            f"governance dispatch skipped: tick={tick_count} reason={result.reason}",
        )
        echo(f"Governance scan skipped: {result.reason}")
