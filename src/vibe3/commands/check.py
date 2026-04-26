"""Check command implementation."""

from typing import Annotated, Any, Literal

import typer
from rich.console import Console

from vibe3.commands.check_support import execute_check_mode
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.check_service import CheckService

app = typer.Typer(
    help="Verify handoff store consistency",
    rich_markup_mode="rich",
)


def _emit_check_details(
    mode: Literal["init", "fix_all", "clean_branch"],
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

    if mode == "fix_all":
        fixed_count = details.get("fixed", 0)
        failed = details.get("failed") or []
        if fixed_count:
            typer.echo(f"  Fixed: {fixed_count} flows")
        for f in failed:
            typer.echo(f"  Failed: {f}", err=True)
        return

    if mode == "clean_branch":
        cleaned = details.get("cleaned") or []
        removed_invalid = details.get("removed_invalid") or []
        failed = details.get("failed") or []
        if cleaned:
            typer.echo(f"  Cleaned: {', '.join(cleaned)}")
        if removed_invalid:
            typer.echo(f"  Removed invalid records: {', '.join(removed_invalid)}")
        for f in failed:
            typer.echo(f"  Failed: {f}", err=True)
        return


@app.callback(invoke_without_command=True)
def check(
    ctx: typer.Context,
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
    clean_branch: Annotated[
        bool,
        typer.Option(
            "--clean-branch",
            help=(
                "Check and clean residual branches for done/aborted flows. "
                "Use this to remove local/remote branches that should have been "
                "cleaned when the flow was marked done or aborted."
            ),
        ),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Verify handoff store consistency.

    Default mode: Check + fix all active flows.
    (Fixable: missing handoff file, missing pr_number, aborted status)

    [green]vibe3 check[/green]         Verify all flows + auto-fix

    [green]vibe3 check --init[/green]  Scan merged PRs + GitHub items,
                         back-fill task_issue_number for all flows.

    [green]vibe3 check --clean-branch[/green]  Clean residual branches
                         for done/aborted flows.
    """
    if trace:
        setup_logging(verbose=2)

    # Mutual exclusion check
    if init and clean_branch:
        typer.echo(
            "Error: --init and --clean-branch are mutually exclusive options.",
            err=True,
        )
        raise typer.Exit(code=1)

    trace_ctx = trace_context(command="check", domain="check") if trace else None
    if trace_ctx:
        trace_ctx.__enter__()

    try:
        service = CheckService()
        mode: Literal["init", "fix_all", "clean_branch"]
        if init:
            mode = "init"
            typer.echo("Scanning merged PRs to back-fill task_issue_number...")
        elif clean_branch:
            mode = "clean_branch"
            typer.echo("Checking for residual branches (done/aborted flows)...")
        else:
            mode = "fix_all"

        result = execute_check_mode(service, mode)

        if result.success:
            typer.echo(f"✓ {result.summary}")
            _emit_check_details(mode, result.details, fix_requested=True)
        else:
            typer.echo(f"✗ {result.summary}", err=True)
            _emit_check_details(mode, result.details, fix_requested=True)
            raise typer.Exit(code=1)

        # Hint for clean-branch after regular check
        if mode == "fix_all":
            Console().print(
                "\n  [dim]Hint: To clean residual branches for done/aborted flows, "
                "use 'vibe3 check --clean-branch'[/]"
            )
    finally:
        if trace_ctx:
            trace_ctx.__exit__(None, None, None)
