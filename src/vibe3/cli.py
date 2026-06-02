#!/usr/bin/env python3
"""
Vibe 3.0 CLI Entry Point
Thin wrapper that sets up Typer app and registers subcommands.
"""

# Bootstrap: ensure local src/ is on sys.path (even with python -I)
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
del _SRC

import os  # noqa: E402
from typing import Annotated, Optional  # noqa: E402

import typer  # noqa: E402
import typer.rich_utils as _ru  # noqa: E402
from loguru import logger  # noqa: E402
from rich import box as _box  # noqa: E402

from vibe3.commands import (  # noqa: E402
    ask,
    check,
    flow,
    handoff,
    inspect,
    internal,
    mcp,
    plan,
    pr,
    review,
    run,
    scan,
    snapshot,
    status,
    task,
)
from vibe3.commands.command_options import FormatOption  # noqa: E402
from vibe3.exceptions import SystemError, UserError  # noqa: E402
from vibe3.observability import setup_logging  # noqa: E402
from vibe3.server import app as serve  # noqa: E402


# -- Remove help panel borders, keep colors --
class _NoBorderPanel(_ru.Panel):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs["box"] = _box.SIMPLE
        kwargs.pop("border_style", None)
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]


_ru.Panel = _NoBorderPanel  # type: ignore[misc]
# -- End panel styling --


app = typer.Typer(
    name="vibe",
    help="""Vibe 3.0 - Development orchestration tool

Three-tier architecture:
  Tier 3 (Cognitive/Governance): Policies, rules, supervisor
  Tier 2 (Skill Layer): Orchestration and context management
  Tier 1 (Shell Layer): Atomic capabilities and state access

Command groups by tier:
  Skill Layer (orchestration):
    flow, task

  Shell Layer (capabilities):
    handoff, inspect, pr, snapshot, ask

  Agent Execution:
    run, plan, review

  Infrastructure/Governance:
    serve, mcp, scan, check

  Utility:
    version, help

Quick start:
  vibe3 flow status              # Show all active flows
  vibe3 task show                # Show current task details
  vibe3 handoff show @plan       # Show plan for current flow

For command details: vibe3 <command> --help
""",
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
app.add_typer(scan.app, name="scan")
app.add_typer(snapshot.app, name="snapshot")
app.add_typer(serve.app, name="serve")
app.add_typer(internal.app, name="internal")
app.add_typer(mcp.app, name="mcp")
app.add_typer(ask.app, name="ask")


@app.command(name="status", hidden=True)
def status_command(
    check: Annotated[
        bool,
        typer.Option("--check", help="显示前先运行完整 vibe3 check"),
    ] = False,
    output_format: FormatOption = "table",
    trace: status.TraceOption = False,
    min_ms: status.TraceMinMsOption = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """[Compatibility] Redirect to task status."""
    status.status(
        check=check,
        output_format=output_format,
        trace=trace,
        min_ms=min_ms,
        json_output=json_output,
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
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
    # Store verbose in context for subcommands to inherit
    ctx.meta["verbose"] = verbose
    setup_logging(verbose=verbose)


@app.command(name="run")
def run_command(
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Instructions to pass to codeagent"),
    ] = None,
    branch: run.BranchOption = None,
    plan: Annotated[
        Optional[str],
        typer.Option(
            "--plan",
            "-p",
            help="Plan reference: file path or '@plan' to use flow's plan_ref",
        ),
    ] = None,
    skill: Annotated[
        Optional[str],
        typer.Option("--skill", "-s", help="Run a skill from skills/<name>/SKILL.md"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="Enable call tracing (set VIBE3_TRACE=1)")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print command and prompt summary without executing",
        ),
    ] = False,
    no_async: run._ASYNC_OPT = False,
    show_prompt: run._SHOW_PROMPT_OPT = False,
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
    fresh_session: Annotated[
        bool,
        typer.Option(
            "--fresh-session",
            help="Skip session resume and start a fresh agent session",
        ),
    ] = False,
    publish: Annotated[
        bool,
        typer.Option("--publish", help="Publish mode: create commit + PR"),
    ] = False,
) -> None:
    """Execute implementation plan or skill using codeagent-wrapper."""
    run.run_command(
        instructions=instructions,
        branch=branch,
        plan=plan,
        skill=skill,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
        agent=agent,
        backend=backend,
        model=model,
        fresh_session=fresh_session,
        publish=publish,
    )


@app.command()
def version() -> None:
    """Show vibe3 version."""
    typer.echo("3.0.0-dev")


@app.command()
def help(
    ctx: typer.Context,
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

    context = click.Context(
        click_app,
        info_name=ctx.info_name or os.environ.get("VIBE3_PROG_NAME") or "vibe3",
        parent=ctx.parent,
    )

    if command:
        click.echo(click_app.get_help(context))
        return

    click.echo(click_app.get_help(context))


def main() -> None:
    """CLI entry point with unified error handling."""
    # Support -h as --help shorthand (globally replace all positions)
    sys.argv = ["--help" if a == "-h" else a for a in sys.argv]
    prog_name = os.environ.get("VIBE3_PROG_NAME") or Path(sys.argv[0]).name or "vibe3"

    try:
        app(prog_name=prog_name)

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
