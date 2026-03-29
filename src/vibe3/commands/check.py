"""Check command implementation."""

from typing import Annotated, Any, Literal

import typer

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.check_service import CheckService

app = typer.Typer(
    help="Verify handoff store consistency",
    rich_markup_mode="rich",
)


def _emit_check_details(
    mode: Literal["default", "init", "all", "fix", "fix_all"],
    details: dict[str, Any],
    *,
    fix_requested: bool,
) -> None:
    """Render mode-specific check details for CLI visibility."""
    if mode == "init":
        unresolvable = details.get("unresolvable") or []
        if unresolvable:
            typer.echo(
                f"  Unresolvable ({len(unresolvable)} branches — "
                "no linked issues found in PR body):"
            )
            for branch in unresolvable:
                typer.echo(f"    {branch}")
        return

    if mode == "all":
        invalid = details.get("invalid") or []
        for result in invalid:
            branch = getattr(result, "branch", "<unknown>")
            issues = getattr(result, "issues", [])
            typer.echo(f"\n  [{branch}]", err=True)
            for issue in issues:
                typer.echo(f"    - {issue}", err=True)
            typer.echo("    → Run [cyan]vibe3 check --fix[/] to auto-fix", err=True)
        return

    if mode == "fix_all":
        fixed_count = details.get("fixed", 0)
        failed = details.get("failed") or []
        if fixed_count:
            typer.echo(f"  Fixed: {fixed_count} flows")
        for f in failed:
            typer.echo(f"  Failed: {f}", err=True)
        return

    issues = details.get("issues") or []
    for issue in issues:
        typer.echo(f"  - {issue}", err=True)
    if mode == "default" and issues and not fix_requested:
        typer.echo("\n  → Run [cyan]vibe3 check --fix[/] to auto-fix", err=True)


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

      [green]vibe3 check --fix --all[/green]  Check + fix all flows

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
        mode: Literal["default", "init", "all", "fix", "fix_all"] = (
            "init"
            if init
            else (
                "fix_all"
                if fix and all_flows
                else "all" if all_flows else "fix" if fix else "default"
            )
        )
        if mode == "init":
            typer.echo("Scanning merged PRs to back-fill task_issue_number...")
        result = service.execute_check(mode)

        if result.success:
            typer.echo(f"✓ {result.summary}")
            _emit_check_details(mode, result.details, fix_requested=fix)
        else:
            typer.echo(f"✗ {result.summary}", err=True)
            _emit_check_details(mode, result.details, fix_requested=fix)
            raise typer.Exit(code=1)
    finally:
        if trace_ctx:
            trace_ctx.__exit__(None, None, None)
