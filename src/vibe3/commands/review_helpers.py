"""Review command helper functions."""

import json
import subprocess

import typer
from loguru import logger


def run_inspect_json(args: list[str]) -> dict[str, object]:
    """Call vibe inspect subcommand and return JSON result.

    Args:
        args: inspect subcommand argument list

    Returns:
        Parsed JSON dict

    Raises:
        typer.Exit: if inspect call fails
    """
    result = subprocess.run(
        ["uv", "run", "python", "-m", "vibe3", "inspect", *args, "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"inspect failed: {result.stderr}")
        raise typer.Exit(1)
    return json.loads(result.stdout)  # type: ignore
