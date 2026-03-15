#!/usr/bin/env python3
"""
Vibe 3.0 CLI Entry Point
Thin wrapper that sets up Typer app and registers subcommands.
"""
import typer
from vibe3.commands import flow, task, pr

app = typer.Typer(
    name="vibe3",
    help="Vibe 3.0 - Development orchestration tool"
)

# Register subcommands
app.add_typer(flow.app, name="flow")
app.add_typer(task.app, name="task")
app.add_typer(pr.app, name="pr")


@app.command()
def version() -> None:
    """Show vibe3 version."""
    typer.echo("3.0.0-dev")


if __name__ == "__main__":
    app()