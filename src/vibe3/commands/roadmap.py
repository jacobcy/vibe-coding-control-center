#!/usr/bin/env python3
"""Roadmap command handlers (Compatibility layer)."""

import typer

app = typer.Typer(
    help="Vibe Roadmap - Project planning and issue classification",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command()
def help(ctx: typer.Context) -> None:
    """Show help for roadmap commands."""
    typer.echo(ctx.parent.get_help()) if ctx.parent else typer.echo(ctx.get_help())


@app.command()
def classify() -> None:
    """[Compatibility] Classify issues. (Moved to: GitHub Project)"""
    typer.echo("Note: 'roadmap classify' is deprecated. Use GitHub Project.")


@app.command()
def list() -> None:
    """[Compatibility] List roadmap items. (Moved to: status)"""
    typer.echo("Note: 'roadmap list' is deprecated. Redirecting to 'status'...")
    from vibe3.commands.status import status

    status()
