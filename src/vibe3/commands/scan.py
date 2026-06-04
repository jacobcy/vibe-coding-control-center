"""Scan command: standalone governance/supervisor scans without HeartbeatServer."""

import asyncio
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.commands.command_options import _ASYNC_OPT
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.observability import setup_logging

app = typer.Typer(
    help="Run governance and supervisor scans without starting the server",
    no_args_is_help=True,
)


def _execute_governance_internal(material_override: str | None = None) -> None:
    """Execute governance scan via service layer (no facade).

    Direct path for manual governance scan, calling execution layer
    without going through OrchestrationFacade heartbeat chain
    or internal command layer.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from vibe3.services.scan_service import dispatch_governance_execution

    dispatch_governance_execution(material_override=material_override)


def _run_governance_scan(
    material_override: str | None = None, no_async: bool = False
) -> None:
    """Execute governance scan once.

    Async default (no_async=False): dispatches via tmux background session.
    Sync (no_async=True): calls internal dispatch directly.

    Args:
        material_override: Optional governance role to override material rotation
        no_async: Run synchronously (blocking) instead of async tmux session
    """
    if no_async:
        _execute_governance_internal(material_override=material_override)
        logger.bind(domain="orchestra").info("Governance scan completed")
    else:
        from vibe3.execution.governance_sync_runner import run_governance_async
        from vibe3.roles.governance import build_governance_execution_name

        run_governance_async(
            tick_count=0,
            material_override=material_override,
            build_execution_name=build_governance_execution_name,
        )


def _run_governance_scan_dry_run(material_override: str | None = None) -> None:
    """Execute governance scan in dry-run mode via run_governance_sync.

    Uses real-time snapshot (not synthetic context) to preview governance prompt.
    This fixes Issue #803 Problem 1: dry-run must match production execution path.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from vibe3.execution.governance_sync_runner import run_governance_sync
    from vibe3.orchestra.logging import append_governance_event
    from vibe3.roles.governance_factory import build_default_governance_fns

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
    """Execute supervisor scan once via execution layer (no facade).

    Fetches supervisor candidates and calls execution layer directly
    without going through OrchestrationFacade or internal command layer.

    Returns:
        Tuple of (total_issues_scanned, matched_issues_found)
    """
    from vibe3.services.scan_service import (
        dispatch_supervisor_execution,
        fetch_supervisor_candidates,
    )

    config = load_orchestra_config()
    github = GitHubClient()

    # Fetch candidates
    total_scanned, candidates = fetch_supervisor_candidates(github, config.repo)
    matched_count = len(candidates)

    # Dispatch each candidate via execution layer
    for candidate in candidates:
        issue_number = candidate["number"]
        dispatch_supervisor_execution(issue_number=issue_number, no_async=False)

    return total_scanned, matched_count


def _run_supervisor_scan_dry_run() -> None:
    """Execute supervisor scan in dry-run mode, displaying scan plan.

    Shows scan process without actual execution.
    """
    from rich.console import Console

    from vibe3.clients.github_client import GitHubClient
    from vibe3.config.orchestra_settings import load_orchestra_config
    from vibe3.services.scan_service import fetch_supervisor_candidates
    from vibe3.ui.scan_display import display_supervisor_dry_run

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

    from vibe3.services.scan_service import (
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
        from vibe3.ui.scan_display import display_material_list

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
    """Execute both governance and supervisor scans in sequence.

    Governance scan uses internal dispatch directly (no facade).
    Supervisor scan uses internal apply dispatch directly (no facade).
    """
    # Governance: call internal dispatch directly (no facade, no FailedGate)
    _execute_governance_internal(material_override=None)
    logger.bind(domain="orchestra").info("Governance scan completed")

    # Supervisor: call internal dispatch directly (no facade)
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
