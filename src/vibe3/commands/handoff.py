"""Handoff command - Agent handoff chain and events."""

import typer

from vibe3.commands.handoff_read import list_handoffs, show
from vibe3.commands.handoff_write import append, audit, init, plan, report

app = typer.Typer(
    help="Agent handoff chain and events",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register commands
app.command("list")(list_handoffs)
app.command()(show)
app.command()(init)
app.command()(append)
app.command()(plan)
app.command()(report)
app.command()(audit)
