"""Handoff command - Agent handoff chain and events."""

import typer

from vibe3.commands.handoff_read import register_read_commands
from vibe3.commands.handoff_write import register_write_commands

app = typer.Typer(
    help="""Agent handoff chain and events.

Handoff files record agent decisions, plans, and findings.
Use handoff commands to view and manage agent communication.

Stable aliases (preferred):
  @plan     Flow plan ref          @report   Flow report ref
  @audit    Flow audit ref         @indicate Manager directives

Examples:
  vibe3 handoff show @plan         # Show plan for current flow
  vibe3 handoff show @report       # Show execution report
  vibe3 handoff show @audit        # Show review findings
  vibe3 handoff show @indicate     # Show manager directives
  vibe3 handoff show @current      # Show current handoff file
  vibe3 handoff status             # Show handoff chain for current flow
  vibe3 handoff append "Update"    # Add a handoff record
  vibe3 handoff show @task-123/run-1.md  # Show specific artifact
  vibe3 handoff show @vibe/supervisor/apply.md  # Show vibe3 governance material

Handoff targets support four namespaces:
  @vibe/<path>     Vibe3 installation materials (governance docs, prompts, skills)
  @key             Shared artifact (.git/vibe3/handoff/)
  relative/path    Worktree ref (requires --branch for other branches)
  /abs/path        Absolute path (debugging fallback)

For more details: vibe3 handoff <command> --help
""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

register_read_commands(app)
register_write_commands(app)
