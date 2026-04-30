"""Handoff command - Agent handoff chain and events."""

import typer

from vibe3.commands.handoff_read import register_read_commands
from vibe3.commands.handoff_write import register_write_commands

app = typer.Typer(
    help="Agent handoff chain and events",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

register_read_commands(app)
register_write_commands(app)
