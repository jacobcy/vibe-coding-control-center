"""Common utilities for command layer."""

import os
import sys

import typer

from vibe3.commands.check_support import execute_check_mode


def enable_method_trace() -> None:
    """Enable method-level tracing via @trace_method decorator.

    Sets VIBE3_TRACE=1 environment variable.
    Use -v or -vv separately to control log verbosity.
    """
    os.environ["VIBE3_TRACE"] = "1"

    if "VIBE3_TRACE_HINT_SHOWN" not in os.environ:
        os.environ["VIBE3_TRACE_HINT_SHOWN"] = "1"
        print(
            "Trace enabled. To add method tracing:\n"
            "  uv run python scripts/trace_manager.py --add --layer services\n"
            "  uv run python scripts/trace_manager.py --add --layer clients\n"
            "  uv run python scripts/trace_manager.py --add --layer all",
            file=sys.stderr,
        )


def run_full_check_shortcut() -> None:
    """Run the full check shortcut used by status-style commands.

    The status dashboard should still render even if the full check reports
    unfixable issues or raises unexpectedly, but users must see a warning.
    """
    from vibe3.services.check_service import CheckService

    try:
        result = execute_check_mode(CheckService(), "fix_all", show_progress=False)
    except Exception as exc:
        typer.echo(
            f"Warning: vibe3 check failed before status: {exc}",
            err=True,
        )
        return

    if not result.success:
        typer.echo(
            f"Warning: vibe3 check incomplete before status: {result.summary}",
            err=True,
        )
