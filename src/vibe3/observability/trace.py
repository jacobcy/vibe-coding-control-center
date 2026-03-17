"""Runtime call chain tracing for Vibe 3.0.

This module provides tracing support for the --trace flag, enabling:
- Call chain visualization
- Cross-module dependency tracking
- Performance monitoring (future)
- State machine transition logging (future)

Usage:
    from vibe3.observability import Tracer, TraceContext

    # In command entry
    with TraceContext(command="pr draft", domain="pr"):
        tracer = Tracer()
        tracer.trace_call("service.pr.create_draft", args={"title": "Fix bug"})

Reference: docs/v3/infrastructure/05-logging.md (tracing section)
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from loguru import logger


@dataclass
class TraceSpan:
    """A single trace span representing a function call or operation.

    Attributes:
        name: Operation name (e.g., "service.pr.create_draft")
        args: Operation arguments
        result: Operation result (if completed)
        error: Exception if operation failed
    """

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Exception | None = None


class Tracer:
    """Tracer for recording call chains.

    This class provides methods to trace function calls and their results,
    enabling visualization of execution flow.
    """

    def __init__(self) -> None:
        """Initialize tracer."""
        self._spans: list[TraceSpan] = []

    def trace_call(
        self,
        name: str,
        args: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """Record a function call.

        Args:
            name: Operation name
            args: Operation arguments

        Returns:
            TraceSpan for recording result/error
        """
        span = TraceSpan(name=name, args=args or {})
        self._spans.append(span)

        logger.bind(trace=name).debug(f"→ {name}({args or ''})")

        return span

    def get_call_chain(self) -> list[dict[str, Any]]:
        """Get the recorded call chain.

        Returns:
            List of span dictionaries
        """
        return [
            {
                "name": span.name,
                "args": span.args,
                "result": span.result,
                "error": str(span.error) if span.error else None,
            }
            for span in self._spans
        ]


@contextmanager
def trace_context(
    command: str,
    domain: str,
    **metadata: Any,
) -> Iterator[None]:
    """Context manager for tracing a command execution.

    Args:
        command: Command name (e.g., "pr draft")
        domain: Business domain (e.g., "pr", "flow", "task")
        **metadata: Additional trace metadata

    Yields:
        None

    Example:
        with TraceContext(command="pr draft", domain="pr"):
            # Execute command
            pass
    """
    logger.bind(command=command, domain=domain, **metadata).info(f"Starting: {command}")

    try:
        yield
        logger.bind(command=command).success(f"Completed: {command}")
    except Exception:
        logger.bind(command=command).exception(f"Failed: {command}")
        raise


__all__ = ["Tracer", "trace_context", "TraceSpan"]
