#!/usr/bin/env python3
"""Flow command handlers."""

import typer

from vibe3.commands.flow_analysis import register_analysis_commands
from vibe3.commands.flow_lifecycle import register_lifecycle_commands
from vibe3.commands.flow_manage import register_manage_commands
from vibe3.commands.flow_status import register_status_commands

app = typer.Typer(
    help="""Manage logic flows.

Flows track development progress across branches, linking issues, tasks, and PRs.

Examples:
  vibe3 flow status              # Show all active flows
  vibe3 flow show                # Show current branch's flow details
  vibe3 flow show --branch main  # Show specific branch's flow
  vibe3 flow bind 123            # Bind issue #123 to current flow
  vibe3 flow update              # Update flow metadata

For more details on each command: vibe3 flow <command> --help
""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register all command groups
register_lifecycle_commands(app)
register_status_commands(app)
register_manage_commands(app)
register_analysis_commands(app)
