"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.agents.review_agent import ReviewUsecase
from vibe3.agents.review_parser import parse_codex_review
from vibe3.agents.review_pipeline_helpers import build_snapshot_diff, run_inspect_json
from vibe3.agents.review_prompt import make_review_context_builder
from vibe3.agents.runner import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.commands.command_options import (
    _DRY_RUN_OPT,
    _TRACE_OPT,
    _WORKTREE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.commands.pr_helpers import build_base_resolution_usecase
from vibe3.config.settings import VibeConfig
from vibe3.services.flow_service import FlowService
from vibe3.utils.trace import enable_trace

_ASYNC_OPT = Annotated[
    bool,
    typer.Option(
        "--async/--sync",
        help="Run asynchronously in background (default: async)",
    ),
]

app = typer.Typer(
    name="review",
    help="Code review with two modes:\n\n"
    "  pr <number>  - Review existing PR from GitHub (analyzes PR diff)\n"
    "  base [branch] - Review local changes vs base branch (compares snapshots)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _emit_review_result(verdict: str, handoff_file: str | None) -> None:
    """Render review result summary consistently."""
    if verdict in {"ASYNC", "DRY_RUN"}:
        return
    typer.echo(f"\n=== Verdict: {verdict} ===")
    if handoff_file:
        typer.echo(f"→ Review saved to: {handoff_file}")


def _build_review_usecase(
    flow_service: FlowService | None = None,
) -> ReviewUsecase:
    """Construct review usecase with command-local dependencies."""
    return ReviewUsecase(
        flow_service=flow_service,
        inspect_runner=run_inspect_json,
        snapshot_diff_builder=build_snapshot_diff,
        review_parser=parse_codex_review,
        context_builder=make_review_context_builder,
        execution_service_factory=CodeagentExecutionService,
        command_builder=create_codeagent_command,
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
    async_mode: _ASYNC_OPT = True,
    worktree: _WORKTREE_OPT = False,
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
    usecase = _build_review_usecase()
    request, issue_number, head_branch = usecase.build_pr_review(pr_number)

    if not head_branch and not dry_run:
        typer.echo(
            f"Error: Could not resolve head branch for PR #{pr_number}", err=True
        )
        raise typer.Exit(1)
    branch = head_branch

    result = usecase.execute_review(
        request,
        dry_run,
        instructions,
        issue_number=issue_number,
        pr_number=pr_number,
        branch=branch,
        async_mode=async_mode,
        worktree=worktree,
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
    async_mode: _ASYNC_OPT = True,
    worktree: _WORKTREE_OPT = False,
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

    if async_mode and not dry_run:
        # Parent only schedules tmux async run; child re-enters CLI and computes
        # inspect/snapshot context once. Avoid duplicate precomputation here.
        config = VibeConfig.get_defaults()
        review_task = (
            instructions
            or (config.review.review_prompt if config.review else None)
            or f"Review changes on {current_branch} vs {resolved_base.base_branch}"
        )
        command = create_codeagent_command(
            role="reviewer",
            context_builder=lambda: "",
            task=review_task,
            dry_run=False,
            handoff_kind="review",
            config=config,
            branch=current_branch,
            worktree=worktree,
        )
        CodeagentExecutionService(config).execute(command, async_mode=True)
        return

    usecase = _build_review_usecase(flow_service=flow_service)
    request, issue_number = usecase.build_base_review(
        current_branch,
        resolved_base.base_branch,
    )
    result = usecase.execute_review(
        request,
        dry_run,
        instructions,
        issue_number=issue_number,
        branch=current_branch,
        async_mode=async_mode,
        worktree=worktree,
    )
    _emit_review_result(result.verdict, result.handoff_file)
    if result.verdict in {"BLOCK", "ERROR"}:
        raise typer.Exit(1)
