#!/usr/bin/env python3
"""
Vibe 3.0 CLI Entry Point
Thin wrapper that sets up Typer app and registers subcommands.
"""

import sys
from typing import Annotated, Optional

import typer
import typer.rich_utils as _ru
from loguru import logger
from rich import box as _box

from vibe3.commands import flow, hooks, inspect, pr, review, task
from vibe3.commands.review_gate import review_gate
from vibe3.exceptions import SystemError, UserError
from vibe3.observability import setup_logging


# ── 去掉 help 面板边框，保留颜色 ──────────────────────────────────────────────
class _NoBorderPanel(_ru.Panel):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs["box"] = _box.SIMPLE
        kwargs.pop("border_style", None)
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]


_ru.Panel = _NoBorderPanel  # type: ignore[misc]
# ─────────────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="vibe3",
    help="Vibe 3.0 - Development orchestration tool",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register subcommands
app.add_typer(flow.app, name="flow")
app.add_typer(task.app, name="task")
app.add_typer(pr.app, name="pr")
app.add_typer(inspect.app, name="inspect")
app.add_typer(review.app, name="review")
app.add_typer(hooks.app, name="hooks")
app.command(name="review-gate")(review_gate)


@app.callback()
def main_callback(
    verbose: Annotated[
        int,
        typer.Option(
            "-v",
            "--verbose",
            count=True,
            help="Verbosity (-v INFO, -vv DEBUG)",
            show_default=False,
            metavar="",
        ),
    ] = 0,
) -> None:
    """Vibe 3.0 - Development orchestration tool."""
    setup_logging(verbose=verbose)


@app.command()
def version() -> None:
    """Show vibe3 version."""
    typer.echo("3.0.0-dev")


@app.command()
def help(
    command: Annotated[Optional[str], typer.Argument(help="Command name")] = None,
) -> None:
    """Show help for commands.

    Examples:
        vibe3 help
        vibe3 help flow
        vibe3 help inspect pr
    """
    import click

    # 获取底层的 Click 命令
    click_app = typer.main.get_command(app)

    if command:
        # 显示子命令的帮助（简化版本：显示主帮助）
        click.echo(click_app.get_help(click.Context(click_app)))
    else:
        # 显示主帮助
        click.echo(click_app.get_help(click.Context(click_app)))


def main() -> None:
    """CLI entry point with unified error handling."""
    # 支持 -h 作为 --help 的简写（全局替换所有位置）
    sys.argv = ["--help" if a == "-h" else a for a in sys.argv]

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
