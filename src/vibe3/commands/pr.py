"""PR command handlers.

This module provides the main PR command group with all subcommands
organized in separate modules for maintainability.

Public commands:
- create: Create draft PR
- ready: Mark PR as ready for review
- show: Show PR details

Removed from public CLI:
- draft: Replaced by create
- merge: Now handled by flow done / integrate
"""

import typer

from vibe3.commands.pr_create import register_create_command
from vibe3.commands.pr_lifecycle import register_lifecycle_commands
from vibe3.commands.pr_query import register_query_commands

app = typer.Typer(
    help="Manage Pull Requests", no_args_is_help=True, rich_markup_mode="rich"
)

# Register all commands
register_create_command(app)
register_query_commands(app)
register_lifecycle_commands(app)
