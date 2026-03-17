"""Structured logging configuration for Vibe 3.0.

This module provides centralized logging setup with:
- Verbosity control via CLI flags (-v, -vv)
- Structured log format with semantic context binding
- Agent-friendly error tracking with full tracebacks
- Rich console integration for visual feedback

Usage:
    from vibe3.observability import setup_logging

    # In CLI entry point
    setup_logging(verbose=1)  # INFO level

    # In service code
    from loguru import logger

    logger.bind(
        command="pr draft", domain="pr", action="create_draft"
    ).info("Creating draft PR")

Reference: docs/v3/infrastructure/05-logging.md
"""

import sys

from loguru import logger

# Remove default handler
logger.remove()


def setup_logging(verbose: int = 0) -> None:
    """Configure the logging system.

    Args:
        verbose: Verbosity level
            0: ERROR level (concise output)
            1: INFO level (show success/info messages)
            2: DEBUG level (show file:line:function, detailed output)

    Example:
        @app.callback()
        def main(verbose: Annotated[int, typer.Option("-v", count=True)] = 0):
            setup_logging(verbose=verbose)
    """
    level = _get_log_level(verbose)
    format_str = _get_format(level)

    # Console output
    logger.add(
        sys.stderr,
        level=level,
        format=format_str,
        colorize=True,
    )


def _get_log_level(verbose: int) -> str:
    """Convert verbosity flag to log level.

    Args:
        verbose: Verbosity level (0-2)

    Returns:
        Log level string (ERROR/INFO/DEBUG)
    """
    if verbose == 0:
        return "ERROR"
    elif verbose == 1:
        return "INFO"
    else:  # verbose >= 2
        return "DEBUG"


def _get_format(level: str) -> str:
    """Get log format string for the given level.

    DEBUG level includes module:function:line for precise code location.
    Other levels use simplified format.

    Args:
        level: Log level string

    Returns:
        Loguru format string
    """
    if level == "DEBUG":
        # Must include module, function, and line number for agent debugging
        return (
            "<cyan>{time:HH:mm:ss}</cyan> | "
            "<level>{level:8}</level> | "
            "<green>{name}:{function}:{line}</green> | "
            "<level>{message}</level>"
        )
    # Simplified format for INFO/ERROR
    return "<level>{level:8}</level> | <level>{message}</level>"


__all__ = ["setup_logging"]
