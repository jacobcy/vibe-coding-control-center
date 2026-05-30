"""Common utilities for command layer."""

import os

import typer

from vibe3.commands.check_support import execute_check_mode


def validate_trace_options(trace: bool, min_ms: float | None) -> None:
    """Validate trace options combination.

    Args:
        trace: Whether --trace is enabled
        min_ms: The --min-ms value if provided

    Raises:
        typer.Exit: If min_ms is provided without --trace
    """
    if min_ms is not None and not trace:
        typer.echo(
            "Error: --min-ms requires --trace to be enabled",
            err=True,
        )
        raise typer.Exit(1)


def enable_method_trace(min_ms: float | None = None) -> None:
    """Enable method-level tracing via @trace_method decorator.

    Sets VIBE3_TRACE=1 environment variable.
    Use -v or -vv separately to control log verbosity.

    Args:
        min_ms: Minimum duration in milliseconds to show in trace.
            Must be non-negative. None resets to no filtering (0).
    """
    os.environ["VIBE3_TRACE"] = "1"

    from vibe3.observability.trace_method import set_trace_min_ms

    if min_ms is not None:
        set_trace_min_ms(min_ms)
    else:
        set_trace_min_ms(0.0)


def run_full_check_shortcut() -> None:
    """Run the full check shortcut used by status-style commands.

    The status dashboard should still render even if the full check reports
    unfixable issues or raises unexpectedly, but users must see a warning.
    """
    from vibe3.services import CheckService

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
