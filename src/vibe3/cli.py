#!/usr/bin/env python3
"""
Vibe 3.0 CLI Entry Point
Thin wrapper that sets up Typer app and registers subcommands.
"""

import sys
from typing import Annotated, Optional

import typer
import typer.rich_utils as _ru
from loguru import logger
from rich import box as _box

from vibe3.commands import flow, handoff, hooks, inspect, pr, review, task
from vibe3.exceptions import SystemError, UserError
from vibe3.observability import setup_logging
from vibe3.services.check_service import CheckService


# -- Remove help panel borders, keep colors --
class _NoBorderPanel(_ru.Panel):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs["box"] = _box.SIMPLE
        kwargs.pop("border_style", None)
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]


_ru.Panel = _NoBorderPanel  # type: ignore[misc]
# -- End panel styling --


app = typer.Typer(
    name="vibe3",
    help="Vibe 3.0 - Development orchestration tool",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register subcommands
app.add_typer(flow.app, name="flow")
app.add_typer(task.app, name="task")
app.add_typer(pr.app, name="pr")
app.add_typer(inspect.app, name="inspect")
app.add_typer(review.app, name="review")
app.add_typer(hooks.app, name="hooks")
app.add_typer(handoff.app, name="handoff")


@app.callback()
def main_callback(
    verbose: Annotated[
        int,
        typer.Option(
            "-v",
            "--verbose",
            count=True,
            help="Verbosity (-v INFO, -vv DEBUG)",
            show_default=False,
            metavar="",
        ),
    ] = 0,
) -> None:
    """Vibe 3.0 - Development orchestration tool."""
    setup_logging(verbose=verbose)


@app.command()
def version() -> None:
    """Show vibe3 version."""
    typer.echo("3.0.0-dev")


@app.command()
def check(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Auto-fix local issues for current branch (no network required)",
    ),
    all_flows: bool = typer.Option(
        False,
        "--all",
        help="Check all flows in the store, not just current branch",
    ),
    init: bool = typer.Option(
        False,
        "--init",
        help=(
            "Scan merged PRs on GitHub and back-fill missing task_issue_number "
            "for all flows. Requires network. Writes to local store. "
            "Safe to re-run (skips flows that already have task_issue_number)."
        ),
    ),
) -> None:
    """Verify handoff store consistency.

    [bold]Modes:[/bold]

      [green]vibe check[/green]         Check current branch only

      [green]vibe check --all[/green]   Check all flows (report only)

      [green]vibe check --fix[/green]   Auto-fix current branch (local, no network)
                         Fixable: missing handoff file
                         Not fixable locally: missing task_issue_number
                         → use --init for network-dependent fixes

      [green]vibe check --init[/green]  Scan merged PRs + GitHub Project items,
                         back-fill task_issue_number for all flows.
                         Network call to GitHub. Writes to local store.
                         Skips flows that already have task_issue_number.
                         Network call to GitHub. Writes to local store.
                         Skips flows that already have task_issue_number.
    """
    service = CheckService()

    # --init: remote index back-fill
    if init:
        typer.echo("Scanning merged PRs to back-fill task_issue_number...")
        result = service.init_remote_index()
        typer.echo(
            f"✓ Done  total={result.total_flows}  "
            f"updated={result.updated}  skipped={result.skipped}"
        )
        if result.unresolvable:
            typer.echo(
                f"  Unresolvable ({len(result.unresolvable)} branches — "
                "no linked issues found in PR body):"
            )
            for b in result.unresolvable:
                typer.echo(f"    {b}")
        return

    # --all: check every flow
    if all_flows:
        results = service.verify_all_flows()
        invalid = [r for r in results if not r.is_valid]
        if not invalid:
            typer.echo(f"✓ All {len(results)} flows passed")
            return
        typer.echo(f"✗ {len(invalid)}/{len(results)} flows have issues:", err=True)
        for r in invalid:
            typer.echo(f"\n  [{r.branch}]", err=True)
            for issue in r.issues:
                typer.echo(f"    - {issue}", err=True)
        raise typer.Exit(code=1)

    # default: check current branch
    result_single = service.verify_current_flow()
    if result_single.is_valid:
        typer.echo("✓ All checks passed")
        return

    typer.echo("✗ Issues found:", err=True)
    for issue in result_single.issues:
        typer.echo(f"  - {issue}", err=True)

    if fix:
        typer.echo("\nAttempting auto-fix...")
        fix_result = service.auto_fix(result_single.issues)
        if fix_result.success:
            typer.echo("✓ Issues fixed")
        else:
            typer.echo(f"✗ {fix_result.error}", err=True)
            raise typer.Exit(code=1)
    else:
        raise typer.Exit(code=1)


@app.command()
def help(
    command: Annotated[Optional[str], typer.Argument(help="Command name")] = None,
) -> None:
    """Show help for commands.

    Examples:
        vibe3 help
        vibe3 help flow
        vibe3 help inspect pr
    """
    import click

    # Get the underlying Click command
    click_app = typer.main.get_command(app)

    if command:
        # Show subcommand help (simplified: show main help)
        click.echo(click_app.get_help(click.Context(click_app)))
    else:
        # Show main help
        click.echo(click_app.get_help(click.Context(click_app)))


def main() -> None:
    """CLI entry point with unified error handling."""
    # Support -h as --help shorthand (globally replace all positions)
    sys.argv = ["--help" if a == "-h" else a for a in sys.argv]

    try:
        app()

    except UserError as e:
        # User error: concise message
        logger.error(e.message)
        if e.recoverable:
            logger.info("Please check your input and try again")
        sys.exit(1)

    except SystemError:
        # System error: show details
        logger.exception("System error occurred")
        sys.exit(2)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)

    except Exception as e:
        # Unexpected error: full traceback
        logger.exception(f"Unexpected error: {e}")
        sys.exit(99)


if __name__ == "__main__":
    main()
