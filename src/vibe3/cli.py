#!/usr/bin/env python3
"""
Vibe 3.0 CLI Entry Point
Thin wrapper that sets up Typer app and registers subcommands.
"""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
import typer.rich_utils as _ru
from loguru import logger
from rich import box as _box

from vibe3.commands import (
    check,
    flow,
    handoff,
    inspect,
    plan,
    pr,
    prompt_check,
    review,
    run,
    snapshot,
    status,
    task,
)
from vibe3.exceptions import SystemError, UserError
from vibe3.observability import setup_logging
from vibe3.orchestra import serve


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
app.add_typer(plan.app, name="plan")
app.add_typer(pr.app, name="pr")
app.add_typer(inspect.app, name="inspect")
app.add_typer(review.app, name="review")
app.add_typer(handoff.app, name="handoff")
app.add_typer(check.app, name="check")
app.add_typer(snapshot.app, name="snapshot")
app.add_typer(serve.app, name="serve")
app.add_typer(prompt_check.app, name="prompt")


@app.command(name="status")
def status_command(
    all_flows: status.AllOption = False,
    json_output: status.JsonOption = False,
    trace: status.TraceOption = False,
) -> None:
    """Show dashboard of all active flows and orchestra status."""
    status.status(all_flows=all_flows, json_output=json_output, trace=trace)


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


@app.command(name="run")
def run_command(
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Instructions to pass to codeagent"),
    ] = None,
    plan: Annotated[
        Optional[Path],
        typer.Option(
            "--plan", "-p", help="Path to plan file (overrides flow plan_ref)"
        ),
    ] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Alias for --plan (deprecated)"),
    ] = None,
    skill: Annotated[
        Optional[str],
        typer.Option("--skill", "-s", help="Run a skill from skills/<name>/SKILL.md"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print command and prompt without executing"),
    ] = False,
    async_mode: Annotated[
        bool, typer.Option("--async", help="Run asynchronously in background")
    ] = False,
    agent: Annotated[
        Optional[str],
        typer.Option(
            "--agent", help="Override agent preset (e.g., executor, executor-pro)"
        ),
    ] = None,
    backend: Annotated[
        Optional[str],
        typer.Option("--backend", help="Override backend (claude, codex)"),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="Override model (e.g., claude-3-opus)"),
    ] = None,
    worktree: Annotated[
        bool,
        typer.Option(
            "--worktree",
            help=(
                "Pass --worktree to codeagent-wrapper "
                "(new isolated worktree execution)"
            ),
        ),
    ] = False,
) -> None:
    """Execute implementation plan or skill using codeagent-wrapper."""
    resolved_plan = plan or file
    run.run_command(
        instructions=instructions,
        plan=resolved_plan,
        skill=skill,
        trace=trace,
        dry_run=dry_run,
        async_mode=async_mode,
        agent=agent,
        backend=backend,
        model=model,
        worktree=worktree,
    )


@app.command()
def version() -> None:
    """Show vibe3 version."""
    typer.echo("3.0.0-dev")


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

    except SystemError as e:
        # System error: concise fail-fast message without traceback noise
        logger.error(e.message)
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
