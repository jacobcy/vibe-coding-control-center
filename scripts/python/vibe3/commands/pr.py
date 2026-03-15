#!/usr/bin/env python3
"""PR command handlers."""
from typing import Optional

import typer
from rich import print

app = typer.Typer(help="Manage Pull Requests")


@app.command()
def draft(
    title: str = typer.Option(..., help="PR title")
) -> None:
    """Create draft PR."""
    print(f"[green]Creating draft PR:[/] {title}")


@app.command()
def show(
    pr_number: Optional[int] = typer.Argument(None, help="PR number")
) -> None:
    """Show PR details."""
    if pr_number:
        print(f"[cyan]PR #{pr_number}[/]")
    else:
        print("[cyan]Current PR[/]")


@app.command()
def ready(
    pr_number: int = typer.Argument(..., help="PR number")
) -> None:
    """Mark PR as ready for review."""
    print(f"[green]Marking PR #{pr_number} as ready[/]")


@app.command()
def merge(
    pr_number: int = typer.Argument(..., help="PR number")
) -> None:
    """Merge PR."""
    print(f"[green]Merging PR #{pr_number}[/]")