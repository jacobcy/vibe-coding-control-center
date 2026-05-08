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


def _run_governance_scan(tick_count: int | None = None) -> None:
    """Execute governance scan once.

    Args:
        tick_count: Override tick count (bypasses interval gating)
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
        tick_count=tick_count if tick_count is not None else 0,
        config=config,
        dispatch_services=None,  # Not needed for governance scan
        capacity=shared_capacity,
        failed_gate=failed_gate,
    )

    # Trigger governance scan
    # on_heartbeat_tick publishes GovernanceScanStarted event
    # which triggers handle_governance_scan_started
    facade.on_heartbeat_tick()

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
        dispatch_services=None,
        capacity=shared_capacity,
        failed_gate=failed_gate,
    )

    # Trigger supervisor scan
    # on_supervisor_scan publishes SupervisorIssueIdentified events
    await facade.on_supervisor_scan()

    logger.bind(domain="orchestra").info("Supervisor scan completed")


@app.command()
def governance(
    tick: Annotated[
        int | None,
        typer.Option("--tick", "-t", help="Override tick count for governance scan"),
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
        if tick is not None:
            typer.echo(f"  - Using tick count: {tick}")
        return

    _run_governance_scan(tick_count=tick)
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


async def _run_combined_scan_async(tick_count: int | None = None) -> None:
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
        tick_count=tick_count if tick_count is not None else 0,
        config=config,
        dispatch_services=None,
        capacity=shared_capacity,
        failed_gate=failed_gate,
    )

    # Run governance scan first
    facade.on_heartbeat_tick()
    logger.bind(domain="orchestra").info("Governance scan completed")

    # Then run supervisor scan
    await facade.on_supervisor_scan()
    logger.bind(domain="orchestra").info("Supervisor scan completed")


@app.command()
def all(
    tick: Annotated[
        int | None,
        typer.Option("--tick", "-t", help="Override tick count for governance scan"),
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
    """Run both governance and supervisor scans once.

    Equivalent to running 'scan governance' and 'scan supervisor' in sequence.
    """
    setup_logging(verbose=verbose)

    if dry_run:
        typer.echo("DRY RUN: Would run both governance and supervisor scans")
        if tick is not None:
            typer.echo(f"  - Using tick count: {tick}")
        return

    asyncio.run(_run_combined_scan_async(tick_count=tick))
    typer.echo("Combined scan completed")
