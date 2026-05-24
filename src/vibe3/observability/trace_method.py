"""Method-level trace decorator.

This module provides a decorator for tracing method calls with timing.
Separated from commands/common.py to avoid circular imports.
"""

import functools
import os
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


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

            from loguru import logger

            start_time = time.time()
            logger.bind(trace=name, layer=layer).debug(f"→ {name}")

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.bind(trace=name, layer=layer).debug(f"✓ {name} ({elapsed:.3f}s)")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.bind(trace=name, layer=layer).debug(
                    f"✗ {name} ({elapsed:.3f}s): {e}"
                )
                raise

        return wrapper  # type: ignore

    return decorator
