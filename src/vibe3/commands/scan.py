"""Scan command: standalone governance/supervisor scans without HeartbeatServer."""

import asyncio
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.commands.command_options import _ASYNC_OPT
from vibe3.config import load_orchestra_config
from vibe3.observability import setup_logging

app = typer.Typer(
    help="Run governance and supervisor scans without starting the server",
    no_args_is_help=True,
)


def _publish_governance_event(
    material_override: str | None = None, tick_count: int = 0
) -> None:
    """Publish GovernanceScanStarted event to the event bus.

    Args:
        material_override: Optional governance role (not used in event,
            preserved for future)
        tick_count: Tick count for the scan (default 0 for manual scans)
    """
    from vibe3.domain import publish
    from vibe3.domain.events.governance import GovernanceScanStarted

    event = GovernanceScanStarted(
        tick_count=tick_count,
        execution_count=0,
        actor="cli:scan-governance",
    )
    publish(event)


def _run_governance_scan(
    material_override: str | None = None, no_async: bool = False
) -> None:
    """Execute governance scan once via event bus.

    Publishes GovernanceScanStarted event, which triggers the domain handler
    to dispatch via ExecutionCoordinator (async tmux).

    Args:
        material_override: Optional governance role (not used in event,
            preserved for future)
        no_async: Deprecated flag (logs warning, always uses async dispatch
            via event bus)
    """
    if no_async:
        logger.warning(
            "--no-async is deprecated; event bus triggers handler "
            "with async tmux dispatch"
        )
    _publish_governance_event(material_override=material_override)
    logger.bind(domain="orchestra").info("Governance scan event published")


def _publish_supervisor_events(
    candidates: list[dict],
) -> None:
    """Publish SupervisorIssueIdentified events for each candidate.

    Args:
        candidates: List of issue candidate dicts with 'number' and 'title' fields
    """
    from vibe3.domain import publish
    from vibe3.models.domain_events import SupervisorIssueIdentified

    for candidate in candidates:
        event = SupervisorIssueIdentified(
            issue_number=candidate["number"],
            issue_title=candidate.get("title", ""),
            supervisor_file="",  # Resolved by handler
            actor="cli:scan-supervisor",
        )
        publish(event)


def _run_governance_scan_dry_run(material_override: str | None = None) -> None:
    """Execute governance scan in dry-run mode via run_governance_sync.

    Uses real-time snapshot (not synthetic context) to preview governance prompt.
    This fixes Issue #803 Problem 1: dry-run must match production execution path.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from vibe3.execution import run_governance_sync
    from vibe3.observability import append_governance_event
    from vibe3.roles import build_default_governance_fns

    # Call internal governance runner with dry_run=True
    # This uses real snapshot instead of synthetic dry-run context
    run_governance_sync(
        tick_count=0,  # Manual scan always uses tick=0
        material_override=material_override,
        dry_run=True,
        show_prompt=True,
        session_id=None,
        governance_fns=build_default_governance_fns(),
        append_event=append_governance_event,
    )


def _run_supervisor_scan() -> tuple[int, int]:
    """Execute supervisor scan once via event bus.

    Fetches supervisor candidates and publishes SupervisorIssueIdentified events
    for each candidate, which triggers the domain handler to dispatch.

    Returns:
        Tuple of (total_issues_scanned, matched_issues_found)
    """
    from vibe3.roles import fetch_supervisor_candidates

    config = load_orchestra_config()
    github = GitHubClient()

    # Fetch candidates
    total_scanned, candidates = fetch_supervisor_candidates(github, config.repo)
    matched_count = len(candidates)

    # Publish events for each candidate
    if candidates:
        _publish_supervisor_events(candidates)

    return total_scanned, matched_count


def _run_supervisor_scan_dry_run() -> None:
    """Execute supervisor scan in dry-run mode, displaying scan plan.

    Shows scan process without actual execution.
    """
    from rich.console import Console

    from vibe3.clients import GitHubClient
    from vibe3.config import load_orchestra_config
    from vibe3.roles import fetch_supervisor_candidates
    from vibe3.ui import display_supervisor_dry_run

    console = Console()
    config = load_orchestra_config()

    # Fetch candidates via service layer
    try:
        github = GitHubClient()
        total_scanned, candidates = fetch_supervisor_candidates(github, config.repo)
    except Exception as e:
        # On error, display empty list
        console.print(f"[yellow]Could not query GitHub: {e}[/yellow]")
        total_scanned = 0
        candidates = []

    # Display via UI layer
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
        _run_governance_scan_dry_run(material_override=role)
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
    if no_async:
        typer.echo("Governance scan completed")


@app.command()
def supervisor(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show scan plan and candidates without executing"
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

    if dry_run:
        _run_supervisor_scan_dry_run()
        return

    # Manual supervisor scan: direct dispatch without facade
    total_scanned, matched_count = _run_supervisor_scan()

    # Display scan results
    if matched_count == 0:
        typer.echo(
            f"Scanned {total_scanned} open issues, "
            f"found 0 issues with supervisor + state/handoff labels"
        )
    else:
        typer.echo(
            f"Scanned {total_scanned} open issues, "
            f"found {matched_count} issue(s) requiring supervisor attention"
        )

    logger.bind(domain="orchestra").info("Supervisor scan completed")


async def _run_combined_scan_async() -> None:
    """Execute both governance and supervisor scans in sequence via event bus.

    Publishes events which trigger domain handlers to dispatch via ExecutionCoordinator.
    """
    # Governance: publish event
    _publish_governance_event(material_override=None)
    logger.bind(domain="orchestra").info("Governance scan event published")

    # Supervisor: publish events
    total_scanned, matched_count = _run_supervisor_scan()

    # Display scan results
    if matched_count == 0:
        typer.echo(
            f"Scanned {total_scanned} open issues, "
            f"found 0 issues with supervisor + state/handoff labels"
        )
    else:
        typer.echo(
            f"Scanned {total_scanned} open issues, "
            f"found {matched_count} issue(s) requiring supervisor attention"
        )

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
