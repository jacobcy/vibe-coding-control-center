"""Check command implementation."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.check_service import CheckService
from vibe3.ui.console import console

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
                "Initialize flows from merged PRs on GitHub. "
                "Scans PR body and GitHub Project items to extract linked issues, "
                "creates flows for merged PRs (status=done), "
                "and back-fills task_issue_number. "
                "Requires network. Writes to local store. "
                "Skips flows that already have task_issue_number."
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
            console.print("Scanning merged PRs to back-fill task_issue_number...")
            result = service.init_remote_index()
            console.print(
                f"[green]✓[/] Done  total={result.total_flows}  "
                f"updated={result.updated}  skipped={result.skipped}"
            )
            if result.unresolvable:
                console.print(
                    f"  Unresolvable ([yellow]{len(result.unresolvable)}[/] branches — "
                    "no linked issues found in PR body):"
                )
                for b in result.unresolvable:
                    console.print(f"    {b}")
            return

        # --all: check every flow
        if all_flows:
            logger.bind(command="check", mode="all").info("Checking all flows")
            results = service.verify_all_flows()
            invalid = [r for r in results if not r.is_valid]
            if not invalid:
                console.print(f"[green]✓[/] All {len(results)} flows passed")
                return

            console.print(f"[red]✗[/] {len(invalid)}/{len(results)} flows have issues:")

            # If --fix is provided with --all, fix all issues
            if fix:
                console.print("\nAttempting auto-fix for all flows...\n")
                fixed_count = 0
                failed_count = 0
                for r in invalid:
                    console.print(r.branch)
                    fix_result = service.auto_fix_for_branch(r.branch, r.issues)
                    if fix_result.success:
                        console.print(f"  [green]✓[/] Fixed {len(r.issues)} issue(s)")
                        fixed_count += 1
                    else:
                        console.print(f"  [red]✗[/] {fix_result.error}")
                        failed_count += 1
                    console.print()

                console.print(f"[green]✓[/] Fixed {fixed_count}/{len(invalid)} flows")
                if failed_count > 0:
                    console.print(f"[red]✗[/] Failed to fix {failed_count} flows")
                    raise typer.Exit(code=1)
                return

            # Without --fix, just report issues
            for r in invalid:
                console.print(f"\n  {r.branch}")
                for issue in r.issues:
                    console.print(f"    - {issue}")
                console.print(
                    "    [dim]→ Run [cyan]vibe3 check --fix --all[/] "
                    "to auto-fix all flows"
                )
            raise typer.Exit(code=1)

        # default: check current branch
        logger.bind(command="check", mode="single").info("Checking current branch")
        result_single = service.verify_current_flow()
        if result_single.is_valid:
            console.print("[green]✓[/] All checks passed")
            return

        console.print(
            f"[red]✗[/] Issues found for branch '[cyan]{result_single.branch}[/]':"
        )
        for issue in result_single.issues:
            console.print(f"  - {issue}")

        if fix:
            console.print("\nAttempting auto-fix...")
            fix_result = service.auto_fix(result_single.issues)
            if fix_result.success:
                console.print("[green]✓[/] All issues fixed")
            else:
                console.print(f"[red]✗[/] {fix_result.error}")
                raise typer.Exit(code=1)
        else:
            console.print("\n  [dim]→ Run [cyan]vibe3 check --fix[/] to auto-fix[/]")
            raise typer.Exit(code=1)

    finally:
        if trace_ctx:
            trace_ctx.__exit__(None, None, None)
