"""Scan command: manual tick 0 entry point for governance/supervisor scans."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.tick import TickPhase, TickRequest, TickSource
from vibe3.observability import setup_logging
from vibe3.services.tick_dispatcher import TickDispatcher
from vibe3.services.tick_planner import TickPlanner

app = typer.Typer(
    help="Run governance and supervisor scans (manual tick 0)",
    no_args_is_help=False,  # Changed: allow no-args to run both phases
)


@app.callback(invoke_without_command=True)
def scan(
    ctx: typer.Context,
    governance: Annotated[
        bool,
        typer.Option(
            "--governance",
            "-g",
            help="Run governance phase (auto-select material "
            "unless --governance-material specified)",
        ),
    ] = False,
    governance_material: Annotated[
        str | None,
        typer.Option(
            "--governance-material",
            "-gm",
            help="Governance material name (e.g., roadmap-intake). "
            "Requires --governance.",
        ),
    ] = None,
    supervisor: Annotated[
        bool,
        typer.Option(
            "--supervisor",
            "-s",
            help="Run supervisor phase (scan candidates "
            "unless --supervisor-issue specified)",
        ),
    ] = False,
    supervisor_issue: Annotated[
        int | None,
        typer.Option(
            "--supervisor-issue",
            "-si",
            help="Supervisor issue number. Requires --supervisor.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview execution plan without running"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Run governance and/or supervisor scans (manual tick 0).

    This is the unified scan entry point using TickPlanner → TickDispatcher.

    Default behavior (no flags): execute both governance and supervisor phases.

    Examples:
        vibe3 scan  # Full manual tick 0
        vibe3 scan --governance  # Governance only, auto-select material
        vibe3 scan --governance --governance-material roadmap-intake
        vibe3 scan --supervisor  # Supervisor scan candidates
        vibe3 scan --supervisor --supervisor-issue 743
        vibe3 scan -g -gm roadmap-intake -s -si 743 --dry-run
    """
    setup_logging(verbose=verbose)

    # If user invokes a subcommand, let Typer handle it
    if ctx.resilient_parsing:
        return

    # Validate mutual dependencies
    if governance_material and not governance:
        typer.echo(
            "Error: --governance-material requires --governance",
            err=True,
        )
        raise typer.Exit(1)

    if supervisor_issue and not supervisor:
        typer.echo(
            "Error: --supervisor-issue requires --supervisor",
            err=True,
        )
        raise typer.Exit(1)

    # Determine which phases to run
    phases: list[TickPhase] = []

    # If no main flags specified, run both phases (default behavior)
    if not governance and not supervisor:
        phases = [TickPhase.GOVERNANCE, TickPhase.SUPERVISOR]
        logger.bind(domain="scan").info(
            "No flags specified, running both phases (default)"
        )
    else:
        # Add phases based on flags
        if governance:
            phases.append(TickPhase.GOVERNANCE)

        if supervisor:
            phases.append(TickPhase.SUPERVISOR)

    # Build TickRequest
    governance_material_value: str | None = None
    if governance:
        governance_material_value = (
            governance_material  # None = auto-select, explicit = use value
        )

    supervisor_issue_numbers: list[int] = []
    if supervisor:
        if supervisor_issue:
            supervisor_issue_numbers = [supervisor_issue]
        # Empty list means "scan candidates" (dispatcher will handle)

    request = TickRequest(
        source=TickSource.MANUAL_SCAN,
        tick_id=0,
        phases=phases,
        governance_material=governance_material_value,
        supervisor_issue_numbers=supervisor_issue_numbers,
        dry_run=dry_run,
    )

    # Load config and create planner
    config = load_orchestra_config()
    planner = TickPlanner(config)

    # Create execution plan
    plan = planner.plan(request, tick_count=0)

    # Dispatch execution
    dispatcher = TickDispatcher(config)
    dispatcher.dispatch(plan)


# Keep old subcommands for backward compatibility during transition
# Mark as deprecated in help text
@app.command(deprecated=True)
def governance(
    role: Annotated[
        str | None,
        typer.Option(
            "--role",
            "-r",
            help="Override governance role",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Build and display prompt without executing"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """[DEPRECATED] Use 'vibe3 scan --governance' instead."""
    typer.echo(
        "Warning: 'scan governance' is deprecated. Use 'scan --governance' instead.",
        err=True,
    )

    # Map old parameters to new unified command
    phases = [TickPhase.GOVERNANCE]
    request = TickRequest(
        source=TickSource.MANUAL_SCAN,
        tick_id=0,
        phases=phases,
        governance_material=role,
        supervisor_issue_numbers=[],
        dry_run=dry_run,
    )

    config = load_orchestra_config()
    planner = TickPlanner(config)
    plan = planner.plan(request, tick_count=0)

    dispatcher = TickDispatcher(config)
    dispatcher.dispatch(plan)


@app.command(deprecated=True)
def supervisor(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show scan plan without executing"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """[DEPRECATED] Use 'vibe3 scan --supervisor' instead."""
    typer.echo(
        "Warning: 'scan supervisor' is deprecated. Use 'scan --supervisor' instead.",
        err=True,
    )

    # Map to new unified command
    phases = [TickPhase.SUPERVISOR]
    request = TickRequest(
        source=TickSource.MANUAL_SCAN,
        tick_id=0,
        phases=phases,
        governance_material=None,
        supervisor_issue_numbers=[],  # Empty = scan candidates
        dry_run=dry_run,
    )

    config = load_orchestra_config()
    planner = TickPlanner(config)
    plan = planner.plan(request, tick_count=0)

    dispatcher = TickDispatcher(config)
    dispatcher.dispatch(plan)


@app.command(deprecated=True)
def all(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show plans without executing"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """[DEPRECATED] Use 'vibe3 scan' (no flags) instead."""
    typer.echo(
        "Warning: 'scan all' is deprecated. Use 'scan' (no flags) instead.",
        err=True,
    )

    # Map to new unified command
    phases = [TickPhase.GOVERNANCE, TickPhase.SUPERVISOR]
    request = TickRequest(
        source=TickSource.MANUAL_SCAN,
        tick_id=0,
        phases=phases,
        governance_material=None,  # Auto-select
        supervisor_issue_numbers=[],  # Scan candidates
        dry_run=dry_run,
    )

    config = load_orchestra_config()
    planner = TickPlanner(config)
    plan = planner.plan(request, tick_count=0)

    dispatcher = TickDispatcher(config)
    dispatcher.dispatch(plan)
