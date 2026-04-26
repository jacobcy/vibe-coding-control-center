"""Handoff command - Agent handoff chain and events."""

import typer

from vibe3.commands.handoff_read import show, status
from vibe3.commands.handoff_write import (
    append,
    audit,
    indicate,
    init,
    plan,
    report,
    verdict,
)

app = typer.Typer(
    help="Agent handoff chain and events",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register commands
app.command()(show)
app.command()(status)
app.command()(init)
app.command()(append)
app.command()(plan)
app.command()(report)
app.command()(indicate)
app.command()(audit)
app.command()(verdict)
