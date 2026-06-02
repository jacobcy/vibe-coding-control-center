"""Init command implementation."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    help="Initialize vibe3 configuration for a project",
    rich_markup_mode="rich",
)

_CONFIG_YAML_TEMPLATE = """profile: default
adapter: default
"""

_GITIGNORE_ENTRIES = [
    ".vibe/",
    ".worktrees/",
    ".agent/plans/",
    ".agent/reports/",
    "temp/",
]

_AGENTS_MD_TEMPLATE = """# AI Agent Guide

This file serves as the entry point for AI agents working on this project.

## Project Overview

<!-- Describe your project here -->

## Key Workflows

<!-- Document your key workflows here -->

## Essential Reading

<!-- List essential documentation files here -->

## Development Setup

<!-- Document how to set up the development environment -->

---
For more details on vibe3 usage, see: https://github.com/anthropics/vibe-coding-control-center
"""


@app.callback(invoke_without_command=True)
def init_command() -> None:
    """Initialize vibe3 configuration for a project.

    Creates minimal necessary file structure:
      - .vibe/config.yaml (minimal template)
      - .gitignore entries (if not present)
      - AGENTS.md (if not present)

    After running this command, use [green]/vibe-project-check[/green] to
    verify your environment and configure manager-bot.
    """
    console = Console()

    # Create .vibe/ directory
    vibe_dir = Path(".vibe")
    vibe_dir.mkdir(exist_ok=True)

    # Create .vibe/config.yaml (skip if exists)
    config_path = vibe_dir / "config.yaml"
    if config_path.exists():
        console.print("[yellow]✓[/yellow] .vibe/config.yaml already exists, skipping")
    else:
        config_path.write_text(_CONFIG_YAML_TEMPLATE)
        console.print("[green]✓[/green] Created .vibe/config.yaml")

    # Update .gitignore
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        existing_content = gitignore_path.read_text()
        existing_lines = {
            line.strip() for line in existing_content.splitlines() if line.strip()
        }

        # Find missing entries
        missing_entries = [e for e in _GITIGNORE_ENTRIES if e not in existing_lines]

        if missing_entries:
            with gitignore_path.open("a") as f:
                f.write("\n# Vibe3 entries\n")
                for entry in missing_entries:
                    f.write(f"{entry}\n")
            console.print(
                f"[green]✓[/green] Added {len(missing_entries)} entries to .gitignore"
            )
        else:
            console.print("[yellow]✓[/yellow] .gitignore already has all entries")
    else:
        gitignore_content = "# Vibe3 entries\n" + "\n".join(_GITIGNORE_ENTRIES) + "\n"
        gitignore_path.write_text(gitignore_content)
        console.print("[green]✓[/green] Created .gitignore with vibe3 entries")

    # Create AGENTS.md (skip if exists)
    agents_md_path = Path("AGENTS.md")
    if agents_md_path.exists():
        console.print("[yellow]✓[/yellow] AGENTS.md already exists, skipping")
    else:
        agents_md_path.write_text(_AGENTS_MD_TEMPLATE)
        console.print("[green]✓[/green] Created AGENTS.md")

    # Print next steps
    console.print()
    console.print(
        Panel(
            "[green]✅ Project initialized successfully![/green]\n\n"
            "[bold]Next Steps:[/bold]\n\n"
            "1. Check project environment (recommended):\n"
            "   [cyan]/vibe-project-check[/cyan]\n\n"
            "2. Configure manager-bot (required for orchestra):\n"
            "   Add [bold]VIBE_MANAGER_GITHUB_TOKEN[/bold] to "
            "[bold]config/keys.env[/bold]\n\n"
            "3. Start orchestra (optional):\n"
            "   [cyan]vibe3 serve[/cyan]\n\n"
            "📖 Documentation: https://github.com/anthropics/vibe-coding-control-center",
            title="",
            border_style="green",
        )
    )
