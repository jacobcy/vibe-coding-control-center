#!/usr/bin/env python3
"""Flow command handlers."""
import json
from typing import Optional

import typer
from rich import print

app = typer.Typer(help="Manage logic flows (branch-centric)")


@app.command()
def new(
    name: str = typer.Argument(..., help="Flow name"),
    branch: Optional[str] = typer.Option(None, help="Base branch")
) -> None:
    """Create a new flow."""
    print(f"[green]Creating flow:[/] {name}")


@app.command()
def bind(
    flow_name: str = typer.Argument(..., help="Flow to bind")
) -> None:
    """Bind current worktree to a flow."""
    print(f"[green]Binding to flow:[/] {flow_name}")


@app.command()
def show(
    flow_name: Optional[str] = typer.Argument(None, help="Flow to show")
) -> None:
    """Show flow details."""
    if flow_name:
        print(f"[cyan]Flow:[/] {flow_name}")
    else:
        print("[cyan]Current flow[/]")


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", help="JSON output")
) -> None:
    """Show flow status."""
    if json_output:
        # Return empty but valid JSON
        typer.echo(json.dumps({}, indent=2))
    else:
        print("[green]Flow status:[/] No active flow")