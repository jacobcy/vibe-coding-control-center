"""Check command implementation."""

from typing import Annotated

import typer
from loguru import logger

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

        # --init: remote index back-fill
        if init:
            logger.bind(command="check", mode="init").info(
                "Scanning merged PRs to back-fill task_issue_number"
            )
            typer.echo("Scanning merged PRs to back-fill task_issue_number...")
            result = service.init_remote_index()
            typer.echo(
                f"✓ Done  total={result.total_flows}  "
                f"updated={result.updated}  skipped={result.skipped}"
            )
            if result.unresolvable:
                typer.echo(
                    f"  Unresolvable ({len(result.unresolvable)} branches — "
                    "no linked issues found in PR body):"
                )
                for b in result.unresolvable:
                    typer.echo(f"    {b}")
            return

        # --all: check every flow
        if all_flows:
            logger.bind(command="check", mode="all").info("Checking all flows")
            results = service.verify_all_flows()
            invalid = [r for r in results if not r.is_valid]
            if not invalid:
                typer.echo(f"✓ All {len(results)} flows passed")
                return
            typer.echo(f"✗ {len(invalid)}/{len(results)} flows have issues:", err=True)
            for r in invalid:
                typer.echo(f"\n  [{r.branch}]", err=True)
                for issue in r.issues:
                    typer.echo(f"    - {issue}", err=True)
                typer.echo("    → Run [cyan]vibe3 check --fix[/] to auto-fix", err=True)
            raise typer.Exit(code=1)

        # default: check current branch
        logger.bind(command="check", mode="single").info("Checking current branch")
        result_single = service.verify_current_flow()
        if result_single.is_valid:
            typer.echo("✓ All checks passed")
            return

        typer.echo(f"✗ Issues found for branch '{result_single.branch}':", err=True)
        for issue in result_single.issues:
            typer.echo(f"  - {issue}", err=True)

        if fix:
            typer.echo("\nAttempting auto-fix...")
            fix_result = service.auto_fix(result_single.issues)
            if fix_result.success:
                typer.echo("✓ All issues fixed")
            else:
                typer.echo(f"✗ {fix_result.error}", err=True)
                raise typer.Exit(code=1)
        else:
            typer.echo(
                "\n  → Run [cyan]vibe3 check --fix[/] to auto-fix",
                err=True,
            )
            raise typer.Exit(code=1)

    finally:
        if trace_ctx:
            trace_ctx.__exit__(None, None, None)
