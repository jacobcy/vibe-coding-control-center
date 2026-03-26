"""Common utilities for command layer."""

from contextlib import nullcontext
from typing import Any

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
