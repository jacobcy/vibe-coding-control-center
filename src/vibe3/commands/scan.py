"""Scan command: standalone governance/supervisor scans without HeartbeatServer."""

import asyncio
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.observability import setup_logging

app = typer.Typer(
    help="Run governance and supervisor scans without starting the server",
    no_args_is_help=True,
)


def _execute_governance_internal(material_override: str | None = None) -> None:
    """Execute governance scan via internal dispatch (no facade).

    Direct path for manual governance scan, calling internal_governance_dispatch
    without going through OrchestrationFacade heartbeat chain.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from vibe3.commands.internal import internal_governance_dispatch

    internal_governance_dispatch(
        tick=0,
        material=material_override,
    )


def _run_governance_scan(material_override: str | None = None) -> None:
    """Execute governance scan once via internal dispatch.

    Calls internal_governance_dispatch directly without facade heartbeat chain.

    Args:
        material_override: Optional governance role to override material rotation
    """
    _execute_governance_internal(material_override=material_override)
    logger.bind(domain="orchestra").info("Governance scan completed")


def _run_governance_scan_dry_run(material_override: str | None = None) -> None:
    """Execute governance scan in dry-run mode, displaying prompt without execution.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from rich.console import Console

    from vibe3.config.orchestra_settings import load_orchestra_config
    from vibe3.roles.governance import build_governance_recipe
    from vibe3.services.scan_service import render_governance_prompt_preview
    from vibe3.ui.scan_display import display_governance_dry_run

    console = Console()
    config = load_orchestra_config()
    tick_count = 0  # Dry-run uses tick 0 for consistency

    try:
        # Build recipe to get material name
        recipe = build_governance_recipe(config, tick_count, material_override)
        current_material = recipe.variables.get("supervisor_name")
        if current_material is None:
            console.print("[red]Error: supervisor_name variable not found[/red]")
            raise typer.Exit(1)

        # Extract material name (guaranteed to be str at this point)
        if hasattr(current_material, "value") and current_material.value:
            material_name = str(current_material.value)
        else:
            material_name = str(current_material)

        # Render prompt
        prompt_content = render_governance_prompt_preview(
            config, tick_count, material_override
        )

        # Display via UI layer
        display_governance_dry_run(console, material_name, prompt_content)

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _run_supervisor_scan() -> tuple[int, int]:
    """Execute supervisor scan once via internal apply (no facade).

    Fetches supervisor candidates and calls internal_apply_dispatch directly
    without going through OrchestrationFacade event chain.

    Returns:
        Tuple of (total_issues_scanned, matched_issues_found)
    """
    from vibe3.commands.internal import internal_apply_dispatch
    from vibe3.services.scan_service import fetch_supervisor_candidates

    config = load_orchestra_config()
    github = GitHubClient()

    # Fetch candidates
    candidates = fetch_supervisor_candidates(github, config.repo)
    matched_count = len(candidates)

    # Dispatch each candidate via internal apply
    for candidate in candidates:
        issue_number = candidate["number"]
        internal_apply_dispatch(issue=issue_number, dry_run=False, no_async=False)

    return matched_count, matched_count


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
        candidates = fetch_supervisor_candidates(github, config.repo)
    except Exception as e:
        # On error, display empty list
        console.print(f"[yellow]Could not query GitHub: {e}[/yellow]")
        candidates = []

    # Display via UI layer
    display_supervisor_dry_run(console, candidates)


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
    """Extract description from material file (DEPRECATED - use scan_service).

    This function delegates to scan_service.extract_material_description.

    Args:
        material_name: Material file path or name

    Returns:
        Material description or filename as fallback
    """
    from pathlib import Path

    from vibe3.services.scan_service import extract_material_description

    # Normalize to full path if needed (only for relative governance paths)
    if (
        not material_name.startswith("supervisor/governance/")
        and not Path(material_name).is_absolute()
    ):
        material_name = f"supervisor/governance/{material_name}"

    # Ensure .md suffix
    if not material_name.endswith(".md"):
        material_name = f"{material_name}.md"

    return extract_material_description(material_name)


def _list_governance_materials() -> None:
    """List available governance materials with descriptions.

    Delegates to service and UI layers for business logic and display.
    """
    from rich.console import Console

    from vibe3.roles.governance import load_governance_material_catalog
    from vibe3.services.scan_service import extract_material_description
    from vibe3.ui.scan_display import display_material_list

    console = Console()

    # Load catalog
    try:
        catalog = load_governance_material_catalog()
    except Exception as exc:
        console.print(f"[red]Error loading material catalog: {exc}[/red]")
        raise typer.Exit(1)

    # Build materials list with descriptions
    materials = []
    for material in catalog:
        description = extract_material_description(material.name)
        materials.append({"name": material.name, "description": description})

    # Display via UI layer
    display_material_list(console, materials)


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
