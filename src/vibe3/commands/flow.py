#!/usr/bin/env python3
"""Flow command handlers."""

import typer

from vibe3.commands.flow_lifecycle import register_lifecycle_commands
from vibe3.commands.flow_manage import register_manage_commands
from vibe3.commands.flow_status import register_status_commands

app = typer.Typer(
    help="Manage logic flows.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register all command groups
register_lifecycle_commands(app)
register_status_commands(app)
register_manage_commands(app)
