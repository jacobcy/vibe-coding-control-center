"""Review command helper functions."""

import json
import subprocess
import sys
from typing import Any

import typer
from loguru import logger


def enable_trace() -> None:
    """启用 DEBUG 日志 + 运行时调用追踪."""
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    indent = [0]

    def _tracer(frame: object, event: str, arg: object) -> Any:
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


def run_inspect_json(args: list[str]) -> dict[str, object]:
    """调用 vibe inspect 子命令，返回 JSON 结果.

    Args:
        args: inspect 子命令参数列表

    Returns:
        解析后的 JSON dict

    Raises:
        typer.Exit: inspect 调用失败
    """
    result = subprocess.run(
        [sys.executable, "-m", "vibe3", "inspect", *args, "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"inspect failed: {result.stderr}")
        raise typer.Exit(1)
    return json.loads(result.stdout)  # type: ignore


def call_codex(context: str) -> str:
    """调用 Codex 执行审核.

    Args:
        context: 完整上下文字符串

    Returns:
        Codex 输出

    Raises:
        RuntimeError: Codex 不可用或执行失败
    """
    try:
        result = subprocess.run(
            ["codex", "exec", "--full-auto"],
            input=context,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Codex failed: {e.stderr}") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Codex timed out after 600s")
    except FileNotFoundError:
        raise RuntimeError("Codex not found. Install: npm install -g @openai/codex")
