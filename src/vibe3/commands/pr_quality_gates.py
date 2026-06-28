"""Quality gates for PR lifecycle commands."""

from __future__ import annotations

from rich.console import Console
from typer import Exit


def run_coverage_gate(console: Console, yes: bool = False) -> None:
    """Run coverage quality gate.

    Args:
        console: Rich console for output
        yes: Bypass coverage check

    Raises:
        Exit: If coverage gate fails
        Exception: If coverage check fails (fail-fast, no interactive bypass)
    """
    if yes:
        console.print("\n[yellow]⚠️  Skipping coverage gate (--yes)[/]")
        return

    from vibe3.analysis import CoverageService

    console.print("\n[cyan]Running coverage check...[/]")

    coverage_service = CoverageService()
    coverage = coverage_service.run_coverage_check()

    if not coverage.all_passing:
        console.print("\n[red]✗ Coverage gate failed[/]")
        overall = coverage.overall_percent
        console.print(f"[yellow]Overall coverage[/]: {overall:.1f}%")

        failing = coverage.get_failing_layers()
        for layer in failing:
            pct = layer.coverage_percent
            console.print(
                f"  [red]✗ {layer.layer_name}[/]: "
                f"{pct:.1f}% < {layer.threshold}% "
                f"(gap: {layer.gap:.1f}%)"
            )

        console.print("\n[dim]Increase coverage or use --yes to bypass[/]")
        raise Exit(1)

    # Display passed coverage
    console.print("\n[green]✓ Coverage gate passed[/]")
    overall = coverage.overall_percent
    console.print(f"[cyan]Overall[/]: {overall:.1f}%")
    svc_pct = coverage.services.coverage_percent
    cli_pct = coverage.clients.coverage_percent
    cmd_pct = coverage.commands.coverage_percent
    console.print(f"  [green]✓ services[/]: {svc_pct:.1f}%")
    console.print(f"  [green]✓ clients[/]: {cli_pct:.1f}%")
    console.print(f"  [green]✓ commands[/]: {cmd_pct:.1f}%")
