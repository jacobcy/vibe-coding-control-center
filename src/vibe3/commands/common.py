"""Common utilities for command layer."""

import os
import sys

import typer

from vibe3.commands.check_support import execute_check_mode


def enable_method_trace(min_ms: float | None = None) -> None:
    """Enable method-level tracing via @trace_method decorator.

    Sets VIBE3_TRACE=1 environment variable.
    Use -v or -vv separately to control log verbosity.

    Args:
        min_ms: Minimum duration in milliseconds to show in trace.
    """
    os.environ["VIBE3_TRACE"] = "1"

    if min_ms is not None and min_ms > 0:
        from vibe3.observability.trace_method import set_trace_min_ms

        set_trace_min_ms(min_ms)

    if "VIBE3_TRACE_HINT_SHOWN" not in os.environ:
        os.environ["VIBE3_TRACE_HINT_SHOWN"] = "1"
        hint = "Trace enabled (output on stderr)."
        if min_ms:
            hint += f" Filtering calls < {min_ms}ms."
        hint += "\nTo add method tracing:\n"
        hint += (
            "  uv run python scripts/trace_manager.py --add --module services\n"
            "  uv run python scripts/trace_manager.py --add --module clients\n"
            "  uv run python scripts/trace_manager.py --add --module all"
        )
        print(hint, file=sys.stderr)


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
