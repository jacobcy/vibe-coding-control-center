"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.commands.command_options import (
    _ASYNC_OPT,
    _DRY_RUN_OPT,
    _TRACE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.commands.pr_helpers import build_base_resolution_usecase
from vibe3.execution.issue_role_sync_runner import (
    run_issue_role_async,
    run_issue_role_sync,
)
from vibe3.roles.review import (
    REVIEW_SYNC_SPEC,
    build_base_review_request,
    build_pr_review_request,
    execute_manual_review,
)
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="review",
    help="Code review with three modes:\n\n"
    "  --issue <n>  - Review issue implementation (orchestra-driven)\n"
    "  pr <number>  - Review existing PR from GitHub (analyzes PR diff)\n"
    "  base [branch] - Review local changes vs base branch (compares snapshots)",
    rich_markup_mode="rich",
)


def _emit_review_result(verdict: str, handoff_file: str | None) -> None:
    """Render review result summary consistently."""
    if verdict in {"ASYNC", "DRY_RUN"}:
        return
    typer.echo(f"\n=== Verdict: {verdict} ===")
    if handoff_file:
        typer.echo(f"→ Review saved to: {handoff_file}")


def _review_issue_impl(
    issue: int,
    report_ref: str | None,
    trace: bool,
    dry_run: bool,
    no_async: bool,
) -> None:
    """Review implementation for an issue via role sync runner."""
    if trace:
        enable_trace()

    _ = report_ref

    if no_async:
        run_issue_role_sync(
            issue_number=issue,
            dry_run=dry_run,
            fresh_session=False,
            spec=REVIEW_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue,
            dry_run=dry_run,
            spec=REVIEW_SYNC_SPEC,
        )


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    issue: Annotated[
        Optional[int],
        typer.Option("--issue", "-i", help="Review issue implementation"),
    ] = None,
    report_ref: Annotated[
        Optional[str],
        typer.Option("--report-ref", help="Report reference for context"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
) -> None:
    """Review with --issue for orchestra-driven review, or use pr/base subcommands."""
    if ctx.invoked_subcommand is not None:
        return
    if issue is not None:
        _review_issue_impl(
            issue=issue,
            report_ref=report_ref,
            trace=trace,
            dry_run=dry_run,
            no_async=no_async,
        )
        return
    typer.echo(ctx.get_help())


@app.command(name="issue")
def issue_command(
    issue: Annotated[int, typer.Argument(help="GitHub issue number")],
    report_ref: Annotated[
        Optional[str],
        typer.Option("--report-ref", help="Report reference for context"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
) -> None:
    """Review implementation for a specific issue (orchestra-driven)."""
    _review_issue_impl(
        issue=issue,
        report_ref=report_ref,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
    )


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Custom prompt (skips context building)"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
) -> None:
    """Review an existing PR by number (fetches diff from GitHub API).

    This command reviews a PR that already exists on GitHub. It analyzes:
    - Changed symbols (functions in diff hunks)
    - Impacted modules (DAG upstream dependencies)
    - Risk score and block status

    Use this to review PRs before merging or providing feedback.

    Example: vibe3 review pr 42 "Focus on security regressions"
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="pr", pr_number=pr_number)
    log.info("Starting PR review")
    typer.echo(f"→ Review: PR #{pr_number}")
    request, issue_number, head_branch = build_pr_review_request(pr_number)

    if not head_branch and not dry_run:
        typer.echo(
            f"Error: Could not resolve head branch for PR #{pr_number}", err=True
        )
        raise typer.Exit(1)
    branch = head_branch

    result = execute_manual_review(
        request=request,
        dry_run=dry_run,
        instructions=instructions,
        issue_number=issue_number,
        pr_number=pr_number,
        branch=branch,
        async_mode=not no_async,
    )
    _emit_review_result(result.verdict, result.handoff_file)
    if result.verdict in {"BLOCK", "ERROR"}:
        raise typer.Exit(1)


@app.command()
def base(
    base_branch: Annotated[
        str | None,
        typer.Argument(
            help="Base branch to compare against (auto-detected if not specified)"
        ),
    ] = None,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Custom prompt (skips context building)"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
) -> None:
    """Review local branch changes against a base branch (compares codebase snapshots).

    This command compares your current local branch state against a base branch.
    It analyzes:
    - Structure diff (file/module/dependency changes)
    - Changed symbols (function-level impact)
    - Impacted modules (DAG upstream dependencies)

    If base_branch is not specified, it will auto-detect the closest parent branch
    (e.g., for refactor/B forked from feature/A, it will compare against feature/A
    instead of main).

    Use this to review local changes before pushing or creating a PR.

    Example: vibe3 review base origin/main "Focus on behavior changes"
    """
    if trace:
        enable_trace()

    flow_service, current_branch = ensure_flow_for_current_branch()
    try:
        resolved_base = build_base_resolution_usecase().resolve_review_base(
            base_branch,
            current_branch=current_branch,
        )
    except RuntimeError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if resolved_base.auto_detected:
        typer.echo(f"→ Auto-detected parent branch: {resolved_base.base_branch}")

    log = logger.bind(
        domain="review",
        action="base",
        current_branch=current_branch,
        base_branch=resolved_base.base_branch,
    )
    log.info("Starting branch review")
    typer.echo(f"→ Review: {current_branch} vs {resolved_base.base_branch}")

    request, issue_number, _ = build_base_review_request(
        current_branch,
        resolved_base.base_branch,
        flow_service=flow_service,
    )
    result = execute_manual_review(
        request=request,
        dry_run=dry_run,
        instructions=instructions,
        issue_number=issue_number,
        branch=current_branch,
        async_mode=not no_async,
    )
    _emit_review_result(result.verdict, result.handoff_file)
    if result.verdict in {"BLOCK", "ERROR"}:
        raise typer.Exit(1)
