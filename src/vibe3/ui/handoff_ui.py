"""Handoff-specific UI rendering helpers."""

from pathlib import Path

from rich.panel import Panel

from vibe3.ui.console import console


def render_handoff_detail(artifact_path: Path) -> None:
    """Display a single handoff artifact file content."""
    content = artifact_path.read_text(encoding="utf-8")
    console.print(Panel(content, title=artifact_path.name))
