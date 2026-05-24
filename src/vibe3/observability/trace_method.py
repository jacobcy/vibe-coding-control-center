"""Method-level trace decorator.

This module provides a decorator for tracing method calls with timing.
Separated from commands/common.py to avoid circular imports.
"""

import atexit
import functools
import os
import sys
import time
from contextvars import ContextVar
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_call_depth: ContextVar[int] = ContextVar("call_depth", default=0)

_trace_stats: dict[tuple[str, str], dict[str, Any]] = {}
_trace_line_count: int = 0
_trace_min_ms: float = 0.0
_trace_max_lines: int = 100
_trace_truncated: bool = False
_atexit_registered: bool = False


class Color:
    """ANSI color codes for trace output."""

    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"


def _format_duration(seconds: float) -> str:
    """Format duration with appropriate unit."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    elif seconds < 1.0:
        return f"{seconds * 1_000:.1f}ms"
    else:
        return f"{seconds:.1f}s"


def set_trace_min_ms(min_ms: float) -> None:
    """Set minimum duration threshold for trace output."""
    global _trace_min_ms
    _trace_min_ms = max(0.0, min_ms)


def set_trace_max_lines(max_lines: int) -> None:
    """Set maximum line count for trace output."""
    global _trace_max_lines
    _trace_max_lines = max(1, max_lines)


def _print_summary() -> None:
    """Print trace summary at program exit."""
    if not _trace_stats:
        if _trace_line_count == 0 and os.environ.get("VIBE3_TRACE", "0") == "1":
            print(
                "\n--trace enabled but no methods are instrumented.\n"
                "Run: uv run python scripts/trace_manager.py --add --module all",
                file=sys.stderr,
            )
        return

    stats_list = list(_trace_stats.values())
    total_time = sum(s["duration"] for s in stats_list)
    sorted_stats = sorted(stats_list, key=lambda s: s["duration"], reverse=True)[:5]

    use_color = sys.stderr.isatty()
    yellow = Color.YELLOW if use_color else ""
    reset = Color.RESET if use_color else ""

    print(f"\n{yellow}--- Trace summary ---{reset}", file=sys.stderr)
    if _trace_truncated:
        print(
            f"{yellow}Output truncated at {_trace_max_lines} lines. "
            f"Use --min-ms to filter fast calls.{reset}",
            file=sys.stderr,
        )
    print(f"Total traced time: {_format_duration(total_time)}", file=sys.stderr)
    print("Top 5 by duration:", file=sys.stderr)

    for i, stat in enumerate(sorted_stats, 1):
        calls_str = f"({stat['calls']} call{'s' if stat['calls'] > 1 else ''})"
        print(
            f"  {i}. {stat['name']} [{stat['layer']}] "
            f"{_format_duration(stat['duration'])} {calls_str}",
            file=sys.stderr,
        )


def _register_atexit() -> None:
    """Register summary printer at program exit (once)."""
    global _atexit_registered
    if not _atexit_registered:
        _atexit_registered = True
        atexit.register(_print_summary)


def trace_method(
    name: str,
    layer: str = "service",
) -> Callable[[F], F]:
    """Decorator to trace method calls with timing.

    Args:
        name: Method name (e.g., "FlowService.show")
        layer: Layer name ("service", "client", "analysis")

    Returns:
        Decorator function

    Note:
        Only enabled when VIBE3_TRACE=1 environment variable is set.
        Output goes to stderr with indentation showing call hierarchy.

    Example:
        @trace_method("FlowService.show", layer="service")
        def show(self, branch: str) -> FlowResult:
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if os.environ.get("VIBE3_TRACE", "0") != "1":
                return func(*args, **kwargs)

            _register_atexit()

            depth = _call_depth.get()
            _call_depth.set(depth + 1)

            indent = "│   " * depth
            use_color = sys.stderr.isatty()

            start_time = time.perf_counter()
            label = f"[{layer}] {name}"

            global _trace_line_count, _trace_truncated

            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time

                key = (name, layer)
                if key in _trace_stats:
                    _trace_stats[key]["duration"] += elapsed
                    _trace_stats[key]["calls"] += 1
                else:
                    _trace_stats[key] = {
                        "name": name,
                        "layer": layer,
                        "duration": elapsed,
                        "calls": 1,
                    }

                elapsed_ms = elapsed * 1000
                should_show = _trace_min_ms <= 0 or elapsed_ms >= _trace_min_ms

                if should_show and _trace_line_count < _trace_max_lines:
                    call_indicator = (
                        f"{Color.CYAN}\u2192{Color.RESET}" if use_color else "\u2192"
                    )
                    print(f"{indent}{call_indicator} {label}", file=sys.stderr)
                    _trace_line_count += 1

                    return_indicator = (
                        f"{Color.GREEN}\u2190{Color.RESET}" if use_color else "\u2190"
                    )
                    print(
                        f"{indent}{return_indicator} {label} "
                        f"[{_format_duration(elapsed)}]",
                        file=sys.stderr,
                    )
                    _trace_line_count += 1
                elif not _trace_truncated and _trace_line_count >= _trace_max_lines:
                    _trace_truncated = True

                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time

                key = (name, layer)
                if key in _trace_stats:
                    _trace_stats[key]["duration"] += elapsed
                    _trace_stats[key]["calls"] += 1
                else:
                    _trace_stats[key] = {
                        "name": name,
                        "layer": layer,
                        "duration": elapsed,
                        "calls": 1,
                    }

                if _trace_line_count < _trace_max_lines:
                    call_indicator = (
                        f"{Color.CYAN}\u2192{Color.RESET}" if use_color else "\u2192"
                    )
                    print(f"{indent}{call_indicator} {label}", file=sys.stderr)
                    _trace_line_count += 1

                    error_indicator = (
                        f"{Color.RED}\u2717{Color.RESET}" if use_color else "\u2717"
                    )
                    print(
                        f"{indent}{error_indicator} {label} raised "
                        f"{type(e).__name__} [{_format_duration(elapsed)}]",
                        file=sys.stderr,
                    )
                    _trace_line_count += 1

                raise
            finally:
                _call_depth.set(depth)

        return wrapper  # type: ignore

    return decorator
