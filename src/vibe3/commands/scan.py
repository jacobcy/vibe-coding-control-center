"""Scan command: standalone governance/supervisor scans without HeartbeatServer."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Annotated, Any

import typer
from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.commands.command_options import _ASYNC_OPT
from vibe3.config import load_orchestra_config
from vibe3.observability import setup_logging

if TYPE_CHECKING:
    from vibe3.models import ExecutionLaunchResult

app = typer.Typer(
    help="Run governance and supervisor scans without starting the server",
    no_args_is_help=True,
)


def _publish_and_wait_governance_event(
    material_override: str | None = None, tick_count: int = 0
) -> ExecutionLaunchResult | None:
    """Publish GovernanceScanStarted event and wait for handler result."""
    from vibe3.domain import GovernanceScanStarted
    from vibe3.models import ExecutionLaunchResult, publish_and_wait

    event = GovernanceScanStarted(
        tick_count=tick_count,
        execution_count=0,
        material_override=material_override,
        actor="cli:scan-governance",
    )
    result = publish_and_wait(event)  # type: ignore[operator]
    if result is None:
        return None
    assert isinstance(result, ExecutionLaunchResult)
    return result


def _run_governance_scan(
    material_override: str | None = None, no_async: bool = False
) -> None:
    """Execute governance scan once via event bus."""
    from rich.console import Console

    from vibe3.domain import register_event_handlers
    from vibe3.ui import display_execution_result

    register_event_handlers()

    if no_async:
        logger.warning(
            "--no-async is deprecated and ignored. Event bus now triggers handler "
            "with async tmux dispatch. For synchronous execution, use "
            "'vibe3 internal governance' directly."
        )

    result = _publish_and_wait_governance_event(material_override=material_override)

    if result:
        console = Console()
        display_execution_result(console, result)
    else:
        logger.bind(domain="orchestra").info(
            "Governance scan completed (no result returned from handler)"
        )


def _publish_and_wait_supervisor_events(
    candidates: list[dict[str, Any]],
) -> list[ExecutionLaunchResult | None]:
    """Publish SupervisorIssueIdentified events and wait for results.

    Args:
        candidates: List of issue candidate dicts with 'number' and 'title' fields

    Returns:
        List of ExecutionLaunchResult from handlers, one per candidate.
        None entries for candidates where handler returned None.

    Note:
        supervisor_file is left empty and resolved by the domain handler.
        Backend/model information is populated by the handler from agent preset.
    """
    from vibe3.domain import SupervisorIssueIdentified
    from vibe3.models import ExecutionLaunchResult, publish_and_wait

    results: list[ExecutionLaunchResult | None] = []
    for candidate in candidates:
        event = SupervisorIssueIdentified(
            issue_number=candidate["number"],
            issue_title=candidate.get("title", ""),
            supervisor_file="",  # Resolved by handler
            actor="cli:scan-supervisor",
        )
        result = publish_and_wait(event)  # type: ignore[operator]
        if result is None or not isinstance(result, ExecutionLaunchResult):
            results.append(None)
        else:
            results.append(result)
    return results


def _run_governance_scan_dry_run(
    material_override: str | None = None, show_prompt: bool = False
) -> None:
    """Execute governance scan in dry-run mode via run_governance_sync.

    Uses real-time snapshot (not synthetic context) to preview governance prompt.
    This fixes Issue #803 Problem 1: dry-run must match production execution path.

    Displays result via shared display_codeagent_result, consistent with
    plan/run/review --dry-run (PR #3143).

    Args:
        material_override: Optional governance role to override material rotation
        show_prompt: If True, display full prompt content with section markers
    """
    from rich.console import Console

    from vibe3.execution import run_governance_sync
    from vibe3.observability import append_governance_event
    from vibe3.roles import build_default_governance_fns
    from vibe3.ui import display_codeagent_result

    # Call internal governance runner with dry_run=True
    # This uses real snapshot instead of synthetic dry-run context
    result = run_governance_sync(
        tick_count=0,  # Manual scan always uses tick=0
        material_override=material_override,
        dry_run=True,
        show_prompt=show_prompt,
        session_id=None,
        governance_fns=build_default_governance_fns(),
        append_event=append_governance_event,
    )

    if result:
        console = Console()
        display_codeagent_result(console, result, "Governance Scan")


def _display_supervisor_candidates(candidates: list[dict[str, Any]]) -> None:
    """Display supervisor candidates with status."""
    typer.echo("\nCandidates:")
    for c in candidates:
        labels_str = ", ".join(c.get("labels", []))
        status = "Ready for supervisor apply"
        if "state/blocked" in c.get("labels", []):
            status = "Blocked"
        elif "state/done" in c.get("labels", []):
            status = "Completed"
        typer.echo(f"- #{c['number']}: {c['title']}")
        typer.echo(f"  Labels: {labels_str}")
        typer.echo(f"  Status: {status}")


def _display_execution_results(
    results: list[ExecutionLaunchResult | None],
) -> None:
    """Display execution dispatch results."""
    from rich.console import Console

    from vibe3.ui import display_execution_result

    console = Console()
    for result in results:
        if result is not None:
            display_execution_result(console, result, "Supervisor Dispatch")


def _run_supervisor_scan() -> tuple[int, int]:
    """Execute supervisor scan once via event bus.

    Returns:
        Tuple of (total_issues_scanned, matched_issues_found)
    """
    from vibe3.domain import register_event_handlers
    from vibe3.roles import fetch_supervisor_candidates

    register_event_handlers()
    config = load_orchestra_config()
    github = GitHubClient()

    total_scanned, candidates = fetch_supervisor_candidates(github, config.repo)
    matched_count = len(candidates)

    typer.echo("Supervisor scan completed")
    typer.echo(f"Scanned: {total_scanned} open issues")
    typer.echo(f"Found: {matched_count} issue(s) requiring supervisor attention")

    if candidates:
        _display_supervisor_candidates(candidates)
        results = _publish_and_wait_supervisor_events(candidates)
        _display_execution_results(results)

    return total_scanned, matched_count


def _run_supervisor_scan_dry_run(show_prompt: bool = False) -> None:
    """Execute supervisor scan in dry-run mode, displaying scan plan.

    Shows scan process without actual execution. Follows the same architectural
    pattern as governance dry-run: uses CodeagentBackend for Prompt Composition
    display, then shows candidate information.

    Args:
        show_prompt: If True, build and display prompts for candidate issues
    """
    from rich.console import Console

    from vibe3.clients import GitHubClient
    from vibe3.config import load_orchestra_config
    from vibe3.roles import (
        build_supervisor_handoff_payload,
        fetch_supervisor_candidates,
    )
    from vibe3.ui import display_supervisor_dry_run

    console = Console()
    config = load_orchestra_config()

    # Build sample prompt for Prompt Composition display
    # (architectural alignment with governance)
    try:
        sample_prompt, options, _ = build_supervisor_handoff_payload(
            config, 999999, "Sample Issue", annotate_sections=show_prompt
        )
        from vibe3.agents import CodeagentBackend, CodeagentResult
        from vibe3.execution import resolve_display_agent_options

        # Show Prompt Composition via CodeagentBackend (same pattern as governance)
        CodeagentBackend().run(
            prompt=sample_prompt,
            options=options,
            task="supervisor scan",
            dry_run=True,
            show_prompt=show_prompt,
            role="supervisor",
            dry_run_summary={
                "prompt_mode": "handoff",
                "sections": ["supervisor.handoff"],
                "refs": {"role": "supervisor"},
            },
        )

        # Display result via shared function, consistent with plan/run/review/governance
        from vibe3.ui import display_codeagent_result

        effective = resolve_display_agent_options(options)
        display_codeagent_result(
            console,
            CodeagentResult(
                success=True,
                backend=effective.backend,
                model=effective.model,
            ),
            "Supervisor Scan",
        )
    except Exception as e:
        console.print(f"[yellow]Could not build prompt preview: {e}[/yellow]")

    # Fetch and display candidates via service layer
    try:
        github = GitHubClient()
        total_scanned, candidates = fetch_supervisor_candidates(github, config.repo)
    except Exception as e:
        console.print(f"[yellow]Could not query GitHub: {e}[/yellow]")
        total_scanned = 0
        candidates = []

    # Always display scan summary, even with zero candidates
    # (when show_prompt=True and candidates exist, also shows individual prompts)
    display_supervisor_dry_run(console, total_scanned, candidates)


@app.command()
def governance(
    list_materials: Annotated[
        bool,
        typer.Option(
            "--list", help="List available governance materials (exclusive with --role)"
        ),
    ] = False,
    role: Annotated[
        str | None,
        typer.Option(
            "--role",
            "-r",
            help="Override governance role (run without --role to see available)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Build and display prompt without executing"),
    ] = False,
    show_prompt: Annotated[
        bool,
        typer.Option(
            "--show-prompt",
            help="With --dry-run, display full prompt content with section markers",
        ),
    ] = False,
    no_async: _ASYNC_OPT = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Run governance scan once.

    Scans all open issues and triggers governance dispatch for issues
    matching governance rules. Runs once and exits.
    """
    from rich.console import Console

    from vibe3.roles import (
        get_available_governance_materials,
        governance_material_exists,
        list_governance_materials,
    )

    setup_logging(verbose=verbose)

    # Check mutual exclusivity first
    if list_materials and role is not None:
        typer.echo("Error: --list and --role cannot be used together", err=True)
        raise typer.Exit(1)

    # Validate --show-prompt requires --dry-run
    from vibe3.commands.command_options import validate_show_prompt_dependency

    validate_show_prompt_dependency(dry_run, show_prompt)

    # Handle --list option (highest priority)
    if list_materials:
        from vibe3.ui import display_material_list

        console = Console()
        list_governance_materials(console, display_fn=display_material_list)
        return

    available_materials = get_available_governance_materials()

    if role is not None and not governance_material_exists(role):
        typer.echo(
            f"Error: governance material '{role}' does not exist.",
            err=True,
        )
        if available_materials:
            typer.echo(f"Available roles: {', '.join(available_materials)}", err=True)
        raise typer.Exit(1)

    if dry_run:
        # In dry-run mode, build and display the prompt without executing
        _run_governance_scan_dry_run(material_override=role, show_prompt=show_prompt)
        return

    if role is None:
        # No role specified - show guidance
        typer.echo(
            "No --role specified. Using automatic material rotation (tick-based)."
        )
        if available_materials:
            typer.echo(f"Available roles: {', '.join(available_materials)}")
            typer.echo("Use --role <role-name> to specify a particular role.")
        typer.echo("")  # Blank line for readability

    _run_governance_scan(material_override=role, no_async=no_async)


@app.command()
def supervisor(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show scan plan and candidates without executing"
        ),
    ] = False,
    show_prompt: Annotated[
        bool,
        typer.Option(
            "--show-prompt",
            help="With --dry-run, build and display prompts for candidates",
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Run supervisor scan once.

    Scans for issues with supervisor + state/handoff labels and triggers
    supervisor handoff dispatch. Runs once and exits.
    """
    setup_logging(verbose=verbose)

    # Validate --show-prompt requires --dry-run
    from vibe3.commands.command_options import validate_show_prompt_dependency

    validate_show_prompt_dependency(dry_run, show_prompt)

    if dry_run:
        _run_supervisor_scan_dry_run(show_prompt=show_prompt)
        return

    # Manual supervisor scan: direct dispatch without facade
    _run_supervisor_scan()

    logger.bind(domain="orchestra").info("Supervisor scan completed")


async def _run_combined_scan_async() -> None:
    """Execute both governance and supervisor scans in sequence via event bus.

    Publishes events which trigger domain handlers to dispatch via ExecutionCoordinator.
    """
    # Governance: publish event and get result
    result = _publish_and_wait_governance_event(material_override=None)

    if result:
        from rich.console import Console

        from vibe3.ui import display_execution_result

        console = Console()
        display_execution_result(console, result)
    else:
        logger.bind(domain="orchestra").info("Governance scan completed (no result)")

    # Supervisor: publish events and display results
    _run_supervisor_scan()

    logger.bind(domain="orchestra").info("Supervisor scan completed")


@app.command()
def all(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show governance and supervisor plans without executing"
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Run both governance and supervisor scans once.

    Equivalent to running 'scan governance' and 'scan supervisor' in sequence.
    """
    setup_logging(verbose=verbose)

    if dry_run:
        _run_governance_scan_dry_run()
        _run_supervisor_scan_dry_run()
        return

    asyncio.run(_run_combined_scan_async())
    typer.echo("Combined scan completed")
