"""Assets command group for global runtime assets."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from vibe3.assets.constants import ASSETS_DIR
from vibe3.assets.manifest import AssetManifest
from vibe3.assets.sync import AssetSync

app = typer.Typer(help="Global runtime assets management")
console = Console()


@app.command()
def sync() -> None:
    """Synchronize builtin assets to global directory."""
    builtin_dir = Path(__file__).parent.parent.parent.parent / "assets"

    # Allow override via environment
    global_dir = Path(os.environ.get("VIBE_ASSETS_DIR", ASSETS_DIR))

    logger.bind(domain="assets", action="sync").info(
        f"Syncing assets from {builtin_dir} to {global_dir}"
    )

    sync_service = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    result = sync_service.run()

    console.print(f"[green]✓[/green] Synced {result.copied} files")
    if result.skipped > 0:
        console.print(f"[dim]  Skipped {result.skipped} identical files[/dim]")

    if result.errors:
        console.print(f"[red]✗[/red] {len(result.errors)} errors")
        for error in result.errors:
            console.print(f"  [red]-[/red] {error}")


@app.command()
def status() -> None:
    """Show global assets status and manifest information."""
    global_dir = Path(os.environ.get("VIBE_ASSETS_DIR", ASSETS_DIR))

    manifest_path = global_dir / "manifest.json"

    if not manifest_path.exists():
        console.print("[yellow]No assets installed[/yellow]")
        console.print("Run [cyan]vibe3 assets sync[/cyan] to install assets")
        return

    manifest = AssetManifest.load(manifest_path)

    table = Table(title="Global Assets Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Version", manifest.version)
    table.add_row("Files", str(len(manifest.checksums)))
    table.add_row("Location", str(global_dir))

    console.print(table)
