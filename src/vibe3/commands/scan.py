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


def _run_governance_scan_dry_run(material_override: str | None = None) -> None:
    """Execute governance scan in dry-run mode, displaying prompt without execution.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from rich.console import Console
    from rich.panel import Panel

    from vibe3.config.orchestra_settings import load_orchestra_config
    from vibe3.roles.governance import (
        build_governance_recipe,
        render_governance_prompt,
    )

    console = Console()

    # Load config
    config = load_orchestra_config()

    # Determine material (use override or tick-based rotation)
    tick_count = 0  # In dry-run, always use tick 0 for consistency

    try:
        recipe = build_governance_recipe(config, tick_count, material_override)
        current_material = recipe.variables.get("supervisor_name")
        if current_material is None:
            console.print(
                "[red]Error: supervisor_name variable not found in recipe[/red]"
            )
            raise typer.Exit(1)
        if hasattr(current_material, "value"):
            material_name = current_material.value
        else:
            material_name = str(current_material)
    except ValueError as e:
        # Material not found
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Display material information
    console.print("\n[bold]Governance Scan Dry-Run[/bold]")
    console.print(f"[cyan]Material:[/cyan] {material_name}")

    # Build minimal snapshot context for prompt rendering
    # In dry-run, we use minimal/empty context since we're not accessing live data
    from vibe3.roles.governance import _build_issue_context

    snapshot_context = _build_issue_context(
        active_entries=(),
        server_running=False,
        active_flows=0,
        active_worktrees=0,
        queued_issues=(),
        circuit_breaker_state="closed",
        circuit_breaker_failures=0,
        issue_scope_name="dry-run mode",
        scope_note="Dry-run mode: using minimal context for prompt preview",
    )

    # Render the prompt
    try:
        render_result = render_governance_prompt(
            config,
            snapshot_context,
            tick_count=tick_count,
            material_override=material_override,
        )
        prompt_content = render_result.rendered_text
    except Exception as e:
        console.print(f"[red]Error rendering prompt: {e}[/red]")
        raise typer.Exit(1)

    # Display prompt preview
    console.print("\n[bold]Prompt Preview:[/bold]")

    # Display the full prompt in a panel
    console.print(Panel(prompt_content, title="Governance Prompt", border_style="blue"))

    # Display summary
    console.print(f"\n[dim]Prompt length: {len(prompt_content)} characters[/dim]")
    console.print(f"[dim]Material: {material_name}[/dim]")
    console.print("[dim]Mode: dry-run (no execution)[/dim]\n")


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


def _run_supervisor_scan_dry_run() -> None:
    """Execute supervisor scan in dry-run mode, displaying scan plan.

    Shows scan process without actual execution.
    """
    from rich.console import Console
    from rich.table import Table

    from vibe3.clients.github_client import GitHubClient
    from vibe3.config.orchestra_settings import load_orchestra_config
    from vibe3.utils.label_utils import normalize_labels

    console = Console()
    config = load_orchestra_config()

    console.print("\n[bold]Supervisor Scan Dry-Run[/bold]")
    console.print("[cyan]Mode:[/cyan] dry-run (no execution)\n")

    # Simulate the scan process
    console.print("[bold]Scan Process:[/bold]")
    console.print("1. Query open issues with 'supervisor' label")
    console.print("2. Filter by additional 'state/handoff' label")
    console.print("3. For each matching issue:")
    console.print("   - Build supervisor handoff prompt")
    console.print("   - Would dispatch supervisor-apply agent\n")

    # Try to fetch actual issues (if possible)
    try:
        github = GitHubClient()
        raw_issues = github.list_issues(
            limit=50,
            state="open",
            assignee=None,
            repo=config.repo,
        )

        # Filter for supervisor + state/handoff labels
        matching_issues = []
        for item in raw_issues:
            labels = normalize_labels(item.get("labels"))
            if "supervisor" in labels and "state/handoff" in labels:
                matching_issues.append(
                    {
                        "number": item.get("number"),
                        "title": item.get("title", "")[:60],  # Truncate long titles
                        "labels": labels,
                    }
                )

        # Display results
        if matching_issues:
            console.print(
                f"[bold]Found {len(matching_issues)} supervisor candidate(s):[/bold]\n"
            )

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Issue", style="yellow")
            table.add_column("Title", style="white")
            table.add_column("Labels", style="green")

            for issue in matching_issues[:10]:  # Show first 10
                labels_str = ", ".join(
                    sorted(issue["labels"])[:5]
                )  # Show first 5 labels
                table.add_row(f"#{issue['number']}", issue["title"], labels_str)

            console.print(table)

            if len(matching_issues) > 10:
                console.print(f"\n[dim]... and {len(matching_issues) - 10} more[/dim]")

            console.print(
                "\n[dim]In real mode, would dispatch supervisor-apply agent "
                "for each issue[/dim]"
            )
        else:
            console.print(
                "[yellow]No issues found with supervisor + "
                "state/handoff labels[/yellow]\n"
            )
            console.print(
                "[dim]In real mode, would report: 'Scanned X open issues, "
                "found 0 issues requiring supervisor attention'[/dim]"
            )

    except Exception as e:
        console.print(f"[yellow]Could not query GitHub (dry-run limited): {e}[/yellow]")
        console.print("[dim]In real mode, would query live issue data[/dim]")

    console.print("\n[bold]Summary:[/bold]")
    console.print(
        "[dim]• Scan target: Open issues with supervisor + state/handoff labels[/dim]"
    )
    console.print(
        "[dim]• Action: Would build and dispatch supervisor-apply prompts[/dim]"
    )
    console.print("[dim]• Mode: dry-run (no execution)[/dim]\n")


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

    # Check mutual exclusivity first
    if list_materials and role is not None:
        typer.echo("Error: --list and --role cannot be used together", err=True)
        raise typer.Exit(1)

    # Handle --list option (highest priority)
    if list_materials:
        _list_governance_materials()
        return

    if dry_run:
        # In dry-run mode, build and display the prompt without executing
        _run_governance_scan_dry_run(material_override=role)
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
