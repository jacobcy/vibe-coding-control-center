"""Method-level trace decorator.

This module provides a decorator for tracing method calls with timing.
Separated from commands/common.py to avoid circular imports.
"""

import functools
import os
import sys
import time
from contextvars import ContextVar
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# ContextVar to track call depth across async boundaries
_call_depth: ContextVar[int] = ContextVar("call_depth", default=0)


class Color:
    """ANSI color codes for trace output."""

    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    RESET = "\033[0m"


def _format_duration(seconds: float) -> str:
    """Format duration with appropriate unit (µs, ms, or s)."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    elif seconds < 1.0:
        return f"{seconds * 1_000:.1f}ms"
    else:
        return f"{seconds:.1f}s"


def trace_method(
    name: str,
    layer: str = "service",
) -> Callable[[F], F]:
    """装饰器：自动追踪方法调用并记录耗时。

    Args:
        name: 方法名称（如 "FlowService.show"）
        layer: 层级名称（"service" 或 "client"）

    Returns:
        装饰器函数

    Note:
        只有当环境变量 VIBE3_TRACE=1 时才会启用 trace。
        这是避免生产环境性能影响的保护措施。
        输出到 stderr，使用缩进显示调用层级。

    Example:
        @trace_method("FlowService.show", layer="service")
        def show(self, branch: str) -> FlowResult:
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check environment variable at runtime, not at import time
            if os.environ.get("VIBE3_TRACE", "0") != "1":
                return func(*args, **kwargs)

            # Increment call depth
            depth = _call_depth.get()
            _call_depth.set(depth + 1)

            # Build indentation
            indent = "│   " * depth

            # Check if stderr is a terminal for color output
            use_color = sys.stderr.isatty()

            start_time = time.perf_counter()

            # Print entry
            call_indicator = (
                f"{Color.CYAN}\u2192{Color.RESET}" if use_color else "\u2192"
            )
            print(f"{indent}{call_indicator} {name}", file=sys.stderr)

            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time

                # Print exit
                return_indicator = (
                    f"{Color.GREEN}\u2190{Color.RESET}" if use_color else "\u2190"
                )
                print(
                    f"{indent}{return_indicator} {name} "
                    f"[{_format_duration(elapsed)}]",
                    file=sys.stderr,
                )
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start_time

                # Print error
                error_indicator = (
                    f"{Color.RED}\u2717{Color.RESET}" if use_color else "\u2717"
                )
                print(
                    f"{indent}{error_indicator} {name} raised "
                    f"{type(e).__name__} [{_format_duration(elapsed)}]",
                    file=sys.stderr,
                )
                raise
            finally:
                _call_depth.set(depth)

        return wrapper  # type: ignore

    return decorator
