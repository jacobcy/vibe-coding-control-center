"""Trace utilities for debugging and runtime call tracing."""

import sys
from typing import Any

from loguru import logger


def enable_trace() -> None:
    """启用 DEBUG 日志 + 运行时调用追踪.

    This function sets up debug-level logging and a runtime call tracer
    that logs function calls within the vibe3 package.
    """
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    indent = [0]

    def _tracer(frame: object, event: str, arg: object) -> Any:
        """Runtime tracer for logging function calls."""
        import types

        assert isinstance(frame, types.FrameType)
        if event == "call" and "vibe3" in frame.f_code.co_filename:
            fn = frame.f_code.co_name
            logger.debug(
                f"{'  ' * indent[0]}→ "
                f"{frame.f_code.co_filename.split('vibe3/')[-1]}::{fn}()"
            )
            indent[0] += 1
        elif event == "return" and "vibe3" in frame.f_code.co_filename:
            indent[0] = max(0, indent[0] - 1)
        return _tracer

    sys.settrace(_tracer)  # type: ignore[arg-type]
