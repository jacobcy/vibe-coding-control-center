"""Common utilities for command layer."""

from contextlib import nullcontext
from typing import Any

import typer

from vibe3.commands.check_support import execute_check_mode
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context


def trace_scope(trace: bool, command: str, domain: str = "flow", **kwargs: Any) -> Any:
    """Create trace context for command execution.

    Args:
        trace: Enable trace mode
        command: Command name
        domain: Domain name (default: flow)
        **kwargs: Additional context fields

    Returns:
        Trace context manager or nullcontext

    Example:
        >>> with trace_scope(True, "flow show", flow_name="my-feature"):
        ...     pass
    """
    if trace:
        setup_logging(verbose=2)
        return trace_context(command=command, domain=domain, **kwargs)
    return nullcontext()


def run_full_check_shortcut() -> None:
    """Run the full check shortcut used by status-style commands.

    The status dashboard should still render even if the full check reports
    unfixable issues or raises unexpectedly, but users must see a warning.
    """
    from vibe3.services.check_service import CheckService

    try:
        result = execute_check_mode(CheckService(), "fix_all")
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
