#!/usr/bin/env python3
"""
Vibe 3.0 CLI Entry Point
Thin wrapper that sets up Typer app and registers subcommands.
"""

import sys
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands import flow, pr, task
from vibe3.exceptions import SystemError, UserError
from vibe3.observability import setup_logging

app = typer.Typer(name="vibe3", help="Vibe 3.0 - Development orchestration tool")

# Register subcommands
app.add_typer(flow.app, name="flow")
app.add_typer(task.app, name="task")
app.add_typer(pr.app, name="pr")


@app.callback()
def main_callback(
    verbose: Annotated[int, typer.Option("-v", count=True)] = 0,
) -> None:
    """Vibe 3.0 - Development orchestration tool.

    Args:
        verbose: Verbosity level (-v for INFO, -vv for DEBUG)
    """
    setup_logging(verbose=verbose)


@app.command()
def version() -> None:
    """Show vibe3 version."""
    typer.echo("3.0.0-dev")


def main() -> None:
    """CLI entry point with unified error handling."""
    try:
        app()

    except UserError as e:
        # User error: concise message
        logger.error(e.message)
        if e.recoverable:
            logger.info("💡 Please check your input and try again")
        sys.exit(1)

    except SystemError:
        # System error: show details
        logger.exception("❌ System error occurred")
        sys.exit(2)

    except KeyboardInterrupt:
        logger.info("⏹️  Interrupted by user")
        sys.exit(130)

    except Exception as e:
        # Unexpected error: full traceback
        logger.exception(f"❌ Unexpected error: {e}")
        sys.exit(99)


if __name__ == "__main__":
    main()
