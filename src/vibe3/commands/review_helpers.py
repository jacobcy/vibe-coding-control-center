"""Review command helper functions."""

import json
import subprocess
import sys

import typer
from loguru import logger


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
