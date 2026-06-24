"""Shared result display — cross-command display for CodeagentResult."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from vibe3.agents import CodeagentResult


def display_codeagent_result(
    console: Console,
    result: CodeagentResult | None,
    label: str = "Execution",
) -> None:
    """Display CodeagentResult from plan/run/review/scan execution.

    Shared across all six execution paths: plan, run, review, scan governance,
    scan supervisor, and internal manager.

    Args:
        console: Rich Console instance
        result: CodeagentResult from handler execution
        label: Label for the result header (e.g., "Plan", "Run")
    """
    if result is None:
        console.print(f"\n[bold]{label} Result[/bold]")
        console.print("[yellow]No result returned (async mode)[/yellow]\n")
        return

    if result.backend:
        console.print()
        console.print(f"[cyan]Backend:[/cyan] {result.backend}")
    if result.model:
        console.print(f"[cyan]Model:[/cyan] {result.model}")
    if result.spec_ref:
        console.print(f"[cyan]Spec:[/cyan] {result.spec_ref}")
    if result.plan_ref:
        console.print(f"[cyan]Plan:[/cyan] {result.plan_ref}")
    if result.report_ref:
        console.print(f"[cyan]Report:[/cyan] {result.report_ref}")

    console.print(f"\n[bold]{label} Result[/bold]")
    if result.success:
        console.print("[green]✓ Completed successfully[/green]")
    else:
        console.print("[red]✗ Failed[/red]")
        if result.stderr:
            console.print(f"[red]{result.stderr}[/red]")

    if result.log_path:
        console.print(f"[cyan]Log path:[/cyan] {result.log_path}")
    if result.handoff_file:
        console.print(f"[cyan]Handoff:[/cyan] {result.handoff_file}")
    if result.tmux_session:
        console.print(f"[cyan]Tmux session:[/cyan] {result.tmux_session}")

    console.print()  # Blank line for readability
