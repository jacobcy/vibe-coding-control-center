"""Flow command package."""

import typer

from vibe3.commands.flow.binding import bind, blocked
from vibe3.commands.flow.info import list, show, status
from vibe3.commands.flow.lifecycle import aborted, done, new, switch

app = typer.Typer(
    help="Manage logic flows (branch-centric)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register lifecycle commands
app.command(name="new")(new)
app.command(name="switch")(switch)
app.command(name="done")(done)
app.command(name="aborted")(aborted)

# Register info commands
app.command(name="show")(show)
app.command(name="status")(status)
app.command(name="list")(list)

# Register binding commands
app.command(name="bind")(bind)
app.command(name="blocked")(blocked)

__all__ = ["app"]
