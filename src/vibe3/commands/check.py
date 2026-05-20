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
    mode: Literal["init", "fix_all", "clean_branch", "branch"],
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

    if mode == "branch":
        # Branch mode details are already in the summary
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
                "Clean residual resources: terminal flows, expired "
                "agent worktrees (>7d), and expired non-protected "
                "branches (>7d, remote+local)."
            ),
        ),
    ] = False,
    branch: Annotated[
        str | None,
        typer.Option(
            "--branch",
            help="Check a single branch instead of all active flows.",
        ),
    ] = None,
    no_progress: Annotated[
        bool,
        typer.Option(
            "--no-progress",
            help="Disable progress bar for 'all' and 'fix_all' modes.",
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

    [green]vibe3 check --branch <name>[/green]  Verify a single branch
                         instead of all active flows.
    """
    if trace:
        setup_logging(verbose=2)

    # Mutual exclusion check
    options_count = sum([init, clean_branch, branch is not None])
    if options_count > 1:
        typer.echo(
            "Error: --init, --clean-branch, and --branch are "
            "mutually exclusive options.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Validate branch is non-empty when provided
    if branch is not None and not branch.strip():
        typer.echo("Error: --branch requires a non-empty branch name.", err=True)
        raise typer.Exit(code=1)

    trace_ctx = trace_context(command="check", domain="check") if trace else None
    if trace_ctx:
        trace_ctx.__enter__()

    try:
        service = CheckService()
        mode: Literal["init", "fix_all", "clean_branch", "branch"]
        if init:
            mode = "init"
            typer.echo("Scanning merged PRs to back-fill task_issue_number...")
        elif clean_branch:
            mode = "clean_branch"
            typer.echo("Checking for residual branches (done/aborted flows)...")

            # SAFETY CHECK: Require explicit confirmation for destructive operation
            # This prevents accidental cleanup of branches that might still be needed
            if not typer.confirm(
                "This will delete local/remote branches and worktrees. Continue?",
                default=False,
            ):
                typer.echo("Cleanup cancelled.", err=True)
                raise typer.Exit(code=0)
        elif branch:
            mode = "branch"
        else:
            mode = "fix_all"

        result = execute_check_mode(
            service, mode, branch=branch, verbose=trace, show_progress=not no_progress
        )

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
