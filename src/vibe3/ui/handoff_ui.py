"""Handoff-specific UI rendering helpers."""

from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from vibe3.ui.console import console


def render_handoff_list(branch: str, handoffs: list[dict[str, str]]) -> None:
    """Render handoff events as a compact table."""
    table = Table(title=f"Handoff Artifacts: {branch}")
    table.add_column("Time", style="cyan")
    table.add_column("Kind", style="magenta")
    table.add_column("Actor", style="green")
    table.add_column("Detail", style="white")

    for handoff in handoffs:
        table.add_row(
            handoff.get("timestamp", ""),
            handoff.get("kind", ""),
            handoff.get("actor", ""),
            handoff.get("detail", ""),
        )

    console.print(table)


def render_handoff_detail(artifact_path: Path) -> None:
    """Display a single handoff artifact file content."""
    content = artifact_path.read_text(encoding="utf-8")
    console.print(Panel(content, title=artifact_path.name))


def render_handoff_summary(branch: str, stats: dict[str, int]) -> None:
    """Render handoff event count summary."""
    console.print(f"\n[bold]Handoff Summary: {branch}[/bold]")
    console.print(f"  Total artifacts: {stats.get('total', 0)}")
    console.print(f"  Plans: {stats.get('plans', 0)}")
    console.print(f"  Runs: {stats.get('runs', 0)}")
    console.print(f"  Reviews: {stats.get('reviews', 0)}")
    if stats.get("indicates", 0):
        console.print(f"  Indicates: {stats.get('indicates', 0)}")
