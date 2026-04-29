"""Sync execution runner for governance scan.

Provides sync execution with ErrorTrackingService integration,
ensuring API errors are captured for FailedGate threshold checking.
"""

from __future__ import annotations

from loguru import logger
from typer import echo

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.orchestra.logging import append_governance_event
from vibe3.roles.governance import (
    build_governance_snapshot_context,
    render_governance_prompt,
    resolve_governance_options,
)
from vibe3.services.orchestra_status_service import OrchestraStatusService


def run_governance_sync(
    *,
    tick_count: int,
    dry_run: bool = False,
    show_prompt: bool = False,
    session_id: str | None = None,
) -> None:
    """Run governance scan synchronously with error tracking.

    This function is called by `internal governance --no-async` CLI command.
    It rebuilds the runtime snapshot, renders the governance prompt,
    and executes through CodeagentBackend with ErrorTrackingService integration.

    Args:
        tick_count: Tick number for governance material rotation
        dry_run: If True, print command without executing
        show_prompt: If True, print prompt content in dry-run mode
        session_id: Optional session ID for resume
    """
    config = load_orchestra_config()
    flow_manager = FlowManager(config)
    status_service = OrchestraStatusService(config, orchestrator=flow_manager)
    snapshot = status_service.snapshot()

    # Resolve agent options
    options = resolve_governance_options(config)

    # Build prompt via snapshot context and prompt assembler
    snapshot_context = build_governance_snapshot_context(
        snapshot,
        config=config,
        tick_count=tick_count,
    )
    render_result = render_governance_prompt(
        config, snapshot_context, tick_count=tick_count
    )
    prompt_content = render_result.rendered_text

    if dry_run:
        echo(f"-> Governance dry-run: tick={tick_count}")
        if show_prompt:
            echo("--- Prompt ---")
            echo(
                prompt_content[:2000] + "..."
                if len(prompt_content) > 2000
                else prompt_content
            )
        return

    echo(f"-> Executing governance tick={tick_count}...")

    try:
        result = CodeagentBackend().run(
            prompt=prompt_content,
            options=options,
            dry_run=False,
            session_id=session_id,
            cwd=None,  # Governance runs in current worktree
            role="governance",
            show_prompt=False,
        )

        # Log successful completion
        append_governance_event(
            f"governance scan completed tick={tick_count} "
            f"exit_code={result.exit_code}"
        )
        logger.bind(domain="governance", tick=tick_count).success(
            f"Governance scan completed: {result.exit_code}"
        )

    except Exception as exc:
        # Error tracking: classify and record for FailedGate threshold
        from vibe3.exceptions.error_classification import classify_error
        from vibe3.exceptions.error_tracking import ErrorTrackingService

        error_output = f"{type(exc).__name__}: {exc}"
        error_code = classify_error(error_output)

        error_tracking = ErrorTrackingService.get_instance()
        error_tracking.record_error(error_code, str(exc))

        logger.bind(domain="governance", tick=tick_count).error(
            f"Governance scan failed: {error_code} - {exc}"
        )
        append_governance_event(
            f"governance scan failed tick={tick_count} " f"error={error_code}: {exc}"
        )

        # Re-raise for CLI exit code handling
        raise
