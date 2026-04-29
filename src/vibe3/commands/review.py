"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.commands.command_options import (
    _ASYNC_OPT,
    _DRY_RUN_OPT,
    _SHOW_PROMPT_OPT,
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
    execute_manual_review_async,
    execute_manual_review_sync,
)
from vibe3.services.flow_service import FlowService
from vibe3.utils.branch_arg import resolve_branch_arg
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="review",
    help="Code review with three modes:\n\n"
    "  --branch <b> - Review issue implementation (orchestra-driven)\n"
    "  pr <number>  - Review existing PR from GitHub (analyzes PR diff)\n"
    "  base [branch] - Review local changes vs base branch (compares snapshots)",
    rich_markup_mode="rich",
)

BranchOption = Annotated[
    str | None,
    typer.Option("--branch", "-b", help="Branch name or issue number (e.g., 320)"),
]


def _emit_review_result(verdict: str, handoff_file: str | None) -> None:
    """Render review result summary consistently."""
    if verdict in {"ASYNC", "DRY_RUN"}:
        return
    typer.echo(f"\n=== Verdict: {verdict} ===")
    if handoff_file:
        typer.echo(f"-> Review saved to: {handoff_file}")


def _review_branch_impl(
    branch: str,
    trace: bool,
    dry_run: bool,
    no_async: bool,
    show_prompt: bool,
) -> None:
    """Review implementation for a branch via role sync runner."""
    if trace:
        enable_trace()

    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)

    if not flow:
        typer.echo(
            f"Error: No flow for branch '{branch}'.\n"
            "Run 'vibe3 flow update' or 'vibe3 flow bind <issue> --role task' first.",
            err=True,
        )
        raise typer.Exit(1)

    issue_number = flow.task_issue_number

    if not issue_number:
        typer.echo(
            f"Error: No issue linked to flow '{branch}'.\n"
            "Run 'vibe flow bind <issue>' first.",
            err=True,
        )
        raise typer.Exit(1)

    if no_async:
        run_issue_role_sync(
            issue_number=issue_number,
            dry_run=dry_run,
            fresh_session=False,
            show_prompt=show_prompt,
            spec=REVIEW_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue_number,
            dry_run=dry_run,
            spec=REVIEW_SYNC_SPEC,
        )


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    branch: BranchOption = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
) -> None:
    """Review with --branch for orchestra-driven review, or use pr/base subcommands."""
    if ctx.invoked_subcommand is not None:
        return

    if branch is not None or ctx.args:
        # --branch provided or positional arg (legacy issue number)
        target_branch = resolve_branch_arg(branch)
        _review_branch_impl(
            branch=target_branch,
            trace=trace,
            dry_run=dry_run,
            no_async=no_async,
            show_prompt=show_prompt,
        )
        return
    typer.echo(ctx.get_help())


@app.command(name="issue", hidden=True)
def issue_command(
    issue: Annotated[int, typer.Argument(help="GitHub issue number")],
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
) -> None:
    """Legacy: review by issue number (use --branch instead)."""
    from vibe3.services.issue_flow_service import IssueFlowService

    branch = IssueFlowService().canonical_branch_name(issue)
    _review_branch_impl(
        branch=branch,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
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
    typer.echo(f"-> Review: PR #{pr_number}")
    request, issue_number, head_branch = build_pr_review_request(pr_number)

    if not head_branch and not dry_run:
        typer.echo(
            f"Error: Could not resolve head branch for PR #{pr_number}", err=True
        )
        raise typer.Exit(1)
    branch = head_branch

    if no_async or dry_run or not branch:
        result = execute_manual_review_sync(
            request=request,
            dry_run=dry_run,
            instructions=instructions,
            issue_number=issue_number,
            pr_number=pr_number,
            branch=branch,
        )
    else:
        result = execute_manual_review_async(
            request=request,
            instructions=instructions,
            issue_number=issue_number,
            pr_number=pr_number,
            branch=branch,
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
        typer.echo(f"-> Auto-detected parent branch: {resolved_base.base_branch}")

    log = logger.bind(
        domain="review",
        action="base",
        current_branch=current_branch,
        base_branch=resolved_base.base_branch,
    )
    log.info("Starting branch review")
    typer.echo(f"-> Review: {current_branch} vs {resolved_base.base_branch}")

    request, issue_number, _ = build_base_review_request(
        current_branch,
        resolved_base.base_branch,
        flow_service=flow_service,
    )
    if no_async or dry_run:
        result = execute_manual_review_sync(
            request=request,
            dry_run=dry_run,
            instructions=instructions,
            issue_number=issue_number,
            branch=current_branch,
        )
    else:
        result = execute_manual_review_async(
            request=request,
            instructions=instructions,
            issue_number=issue_number,
            branch=current_branch,
        )
    _emit_review_result(result.verdict, result.handoff_file)
    if result.verdict in {"BLOCK", "ERROR"}:
        raise typer.Exit(1)
