"""Scan command: standalone governance/supervisor scans without HeartbeatServer."""

import asyncio
from typing import Annotated

import typer
from loguru import logger

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.observability import setup_logging

app = typer.Typer(
    help="Run governance and supervisor scans without starting the server",
    no_args_is_help=True,
)


def _run_governance_scan(material_override: str | None = None) -> None:
    """Execute governance scan once.

    Creates minimal services and publishes GovernanceScanStarted event.
    Event handlers handle the actual execution via CLI self-invocation.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from vibe3.agents.backends.codeagent import CodeagentBackend
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.domain.handlers import register_event_handlers
    from vibe3.domain.orchestration_facade import OrchestrationFacade
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.orchestra.failed_gate import FailedGate

    # Register event handlers before publishing events
    register_event_handlers()

    # Load config
    config = load_orchestra_config()

    # Initialize services (following _build_server_with_launch_cwd pattern)
    shared_store = SQLiteClient()
    shared_backend = CodeagentBackend()
    failed_gate = FailedGate(store=shared_store)
    shared_capacity = CapacityService(config, shared_store, shared_backend)

    # Check FailedGate before dispatching
    gate_result = failed_gate.check()
    if gate_result.blocked:
        logger.bind(domain="orchestra").error(
            f"Scan blocked by failed gate: {gate_result.reason}"
        )
        typer.echo(f"Scan blocked by failed gate: {gate_result.reason}")
        return

    # Create facade with minimal services for governance scan
    facade = OrchestrationFacade(
        tick_count=0,
        config=config,
        capacity=shared_capacity,
        failed_gate=failed_gate,
    )

    # Trigger governance scan (force=True to skip interval gating for manual trigger)
    # on_heartbeat_tick publishes GovernanceScanStarted event
    # which triggers handle_governance_scan_started
    facade.on_heartbeat_tick(force=True, material_override=material_override)

    logger.bind(domain="orchestra").info("Governance scan completed")


async def _run_supervisor_scan_async() -> None:
    """Execute supervisor scan once (async implementation)."""
    from vibe3.agents.backends.codeagent import CodeagentBackend
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.domain.handlers import register_event_handlers
    from vibe3.domain.orchestration_facade import OrchestrationFacade
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.orchestra.failed_gate import FailedGate

    # Register event handlers before publishing events
    register_event_handlers()

    # Load config
    config = load_orchestra_config()

    # Initialize services
    shared_store = SQLiteClient()
    shared_backend = CodeagentBackend()
    failed_gate = FailedGate(store=shared_store)
    shared_capacity = CapacityService(config, shared_store, shared_backend)

    # Check FailedGate before dispatching
    gate_result = failed_gate.check()
    if gate_result.blocked:
        logger.bind(domain="orchestra").error(
            f"Scan blocked by failed gate: {gate_result.reason}"
        )
        typer.echo(f"Scan blocked by failed gate: {gate_result.reason}")
        return

    # Create facade
    facade = OrchestrationFacade(
        tick_count=0,
        config=config,
        capacity=shared_capacity,
        failed_gate=failed_gate,
    )

    # Trigger supervisor scan
    # on_supervisor_scan publishes SupervisorIssueIdentified events
    total_scanned, matched_count = await facade.on_supervisor_scan()

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


def _get_available_governance_materials() -> list[str]:
    """Fetch available governance materials from catalog.

    Returns list of short material names (without path/suffix).
    """
    try:
        from vibe3.roles.governance import load_governance_material_catalog

        catalog = load_governance_material_catalog()
        materials = []
        for material in catalog:
            # Extract short name:
            # "supervisor/governance/roadmap-intake.md" → "roadmap-intake"
            name = material.name
            if name.startswith("supervisor/governance/"):
                short_name = name.split("/")[-1]
                short_name = (
                    short_name[:-3] if short_name.endswith(".md") else short_name
                )
                materials.append(short_name)
        return sorted(set(materials))
    except Exception:
        # Fallback if catalog cannot be loaded
        return []


def _extract_material_description(material_name: str) -> str:
    """Extract description from material file.

    Reads the first markdown header (# Title) as description.
    Falls back to filename if no title found.

    Args:
        material_name: Material file path or name

    Returns:
        Material description or filename as fallback
    """
    from pathlib import Path

    # Normalize to full path if needed
    if (
        not material_name.startswith("supervisor/governance/")
        and not Path(material_name).is_absolute()
    ):
        material_name = f"supervisor/governance/{material_name}"

    # Ensure .md suffix
    if not material_name.endswith(".md"):
        material_name = f"{material_name}.md"

    material_path = Path(material_name)

    # Try to read title from file
    try:
        if material_path.exists():
            with open(material_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("# "):
                        # Extract title without '# ' prefix
                        return line[2:].strip()
                    # Stop at first non-empty, non-title line
                    if line and not line.startswith("#"):
                        break
    except Exception as e:
        logger.debug(f"Failed to extract description from {material_name}: {e}")
        pass

    # Fallback to filename
    return material_name


def _list_governance_materials() -> None:
    """List available governance materials with descriptions.

    Displays a formatted table with material names and descriptions.
    """
    from rich.console import Console
    from rich.table import Table

    from vibe3.roles.governance import load_governance_material_catalog

    console = Console()

    # Load catalog
    try:
        catalog = load_governance_material_catalog()
    except Exception as exc:
        console.print(f"[red]Error loading material catalog: {exc}[/red]")
        raise typer.Exit(1)

    if not catalog:
        console.print("[yellow]No governance materials found[/yellow]")
        return

    # Build table
    table = Table(title="Available Governance Materials")
    table.add_column("Material", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    for material in catalog:
        # Extract short name
        name = material.name
        if name.startswith("supervisor/governance/"):
            short_name = name.split("/")[-1]
            short_name = short_name[:-3] if short_name.endswith(".md") else short_name
        else:
            short_name = name

        # Extract description
        description = _extract_material_description(material.name)

        table.add_row(short_name, description)

    console.print(table)


@app.command()
def governance(
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
        typer.Option("--dry-run", help="Show what would be done without executing"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Run governance scan once.

    Scans all open issues and triggers governance dispatch for issues
    matching governance rules. Runs once and exits.
    """
    setup_logging(verbose=verbose)

    if dry_run:
        typer.echo("DRY RUN: Would run governance scan")
        return

    # Get available materials for help text
    available_materials = _get_available_governance_materials()

    if role is None:
        # No role specified - show guidance
        typer.echo(
            "No --role specified. Using automatic material rotation (tick-based)."
        )
        if available_materials:
            typer.echo(f"Available roles: {', '.join(available_materials)}")
            typer.echo("Use --role <role-name> to specify a particular role.")
        typer.echo("")  # Blank line for readability

    _run_governance_scan(material_override=role)
    typer.echo("Governance scan completed")


@app.command()
def supervisor(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without executing"),
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
        typer.echo("DRY RUN: Would run supervisor scan")
        return

    asyncio.run(_run_supervisor_scan_async())
    typer.echo("Supervisor scan completed")


async def _run_combined_scan_async() -> None:
    """Execute both governance and supervisor scans in sequence."""
    from vibe3.agents.backends.codeagent import CodeagentBackend
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.domain.handlers import register_event_handlers
    from vibe3.domain.orchestration_facade import OrchestrationFacade
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.orchestra.failed_gate import FailedGate

    # Register event handlers before publishing events
    register_event_handlers()

    # Load config
    config = load_orchestra_config()

    # Initialize services
    shared_store = SQLiteClient()
    shared_backend = CodeagentBackend()
    failed_gate = FailedGate(store=shared_store)
    shared_capacity = CapacityService(config, shared_store, shared_backend)

    # Check FailedGate before dispatching
    gate_result = failed_gate.check()
    if gate_result.blocked:
        logger.bind(domain="orchestra").error(
            f"Scan blocked by failed gate: {gate_result.reason}"
        )
        typer.echo(f"Scan blocked by failed gate: {gate_result.reason}")
        return

    # Create facade
    facade = OrchestrationFacade(
        tick_count=0,
        config=config,
        capacity=shared_capacity,
        failed_gate=failed_gate,
    )

    # Run governance scan first (force=True to skip interval gating for manual trigger)
    facade.on_heartbeat_tick(force=True)
    logger.bind(domain="orchestra").info("Governance scan completed")

    # Then run supervisor scan
    total_scanned, matched_count = await facade.on_supervisor_scan()

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
        typer.Option("--dry-run", help="Show what would be done without executing"),
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
        typer.echo("DRY RUN: Would run both governance and supervisor scans")
        return

    asyncio.run(_run_combined_scan_async())
    typer.echo("Combined scan completed")
