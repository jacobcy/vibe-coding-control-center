"""Check command implementation."""

from typing import Annotated, Literal

import typer

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.check_service import CheckService

app = typer.Typer(
    help="Verify handoff store consistency",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def check(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            help="Auto-fix issues for current branch (may require network)",
        ),
    ] = False,
    all_flows: Annotated[
        bool,
        typer.Option(
            "--all", help="Check all flows in the store, not just current branch"
        ),
    ] = False,
    init: Annotated[
        bool,
        typer.Option(
            "--init",
            help=(
                "Scan merged PRs on GitHub and back-fill missing task_issue_number "
                "for all flows. Requires network. Writes to local store. "
                "Safe to re-run (skips flows that already have task_issue_number)."
            ),
        ),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Verify handoff store consistency.

    [bold]Modes:[/bold]

      [green]vibe3 check[/green]         Check current branch only

      [green]vibe3 check --all[/green]   Check all flows (report only)

      [green]vibe3 check --fix[/green]   Auto-fix current branch
                         Fixable: missing handoff file, missing pr_number

      [green]vibe3 check --init[/green]  Scan merged PRs + GitHub Project items,
                         back-fill task_issue_number for all flows.
                         Network call to GitHub. Writes to local store.
                         Skips flows that already have task_issue_number.
    """
    if trace:
        setup_logging(verbose=2)

    trace_ctx = trace_context(command="check", domain="check") if trace else None
    if trace_ctx:
        trace_ctx.__enter__()

    try:
        service = CheckService()
        mode: Literal["default", "init", "all", "fix"] = (
            "init" if init else "all" if all_flows else "fix" if fix else "default"
        )
        result = service.execute_check(mode)

        if result.success:
            typer.echo(f"✓ {result.summary}")
        else:
            typer.echo(f"✗ {result.summary}", err=True)
            if not fix and mode == "default":
                typer.echo("\n  → Run [cyan]vibe3 check --fix[/] to auto-fix", err=True)
            raise typer.Exit(code=1)
    finally:
        if trace_ctx:
            trace_ctx.__exit__(None, None, None)
