"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated, Optional, cast

import typer
from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.commands.command_options import (
    _DRY_RUN_OPT,
    _TRACE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.commands.review_helpers import build_snapshot_diff, run_inspect_json
from vibe3.config.settings import VibeConfig
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.models.review_runner import AgentOptions
from vibe3.services.context_builder import build_review_context
from vibe3.services.execution_pipeline import ExecutionRequest, run_execution_pipeline
from vibe3.services.label_integration import transition_to_review
from vibe3.services.review_parser import parse_codex_review
from vibe3.utils.trace import enable_trace

_ASYNC_OPT = Annotated[
    bool, typer.Option("--async", help="Run asynchronously in background")
]

app = typer.Typer(
    name="review",
    help="Code review with two modes:\n\n"
    "  pr <number>  - Review existing PR from GitHub (analyzes PR diff)\n"
    "  base [branch] - Review local changes vs base branch (compares snapshots)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _run_review(
    request: ReviewRequest,
    config: VibeConfig,
    dry_run: bool,
    instructions: str | None,
    issue_number: int | None = None,
    pr_number: int | None = None,
) -> None:
    log = logger.bind(domain="review", scope=request.scope.kind)

    # Resolve task message
    task = None
    if pr_number:
        if instructions:
            task = f"审查 PR #{pr_number}: {instructions}"
        elif config.review.review_prompt:
            task = f"审查 PR #{pr_number}: {config.review.review_prompt}"
        else:
            task = f"审查 PR #{pr_number} 的变更"
        log.info("Using PR-specific task")
        typer.echo(f"→ Task: {task}")
    elif instructions:
        task = instructions
        log.info("Using custom task message")
        truncated = instructions[:60]
        suffix = "..." if len(instructions) > 60 else ""
        typer.echo(f"→ Custom task: {truncated}{suffix}")
    elif config.review.review_prompt:
        task = config.review.review_prompt
        log.info("Using configured task from vibe.toml")
    else:
        log.info("Using prompt file only (no custom task)")

    # Build agent options
    options = AgentOptions(
        agent=config.review.agent_config.agent,
        backend=config.review.agent_config.backend,
        model=config.review.agent_config.model,
    )

    # Build execution request
    exec_request = ExecutionRequest(
        role="reviewer",
        context_builder=lambda: build_review_context(request, config),
        options_builder=lambda: options,
        task=task,
        dry_run=dry_run,
        handoff_kind="review",
        handoff_metadata={},
    )

    # Run pipeline
    result = run_execution_pipeline(exec_request)

    if dry_run:
        return

    # Review-specific post-processing
    raw = result.agent_result.stdout
    review = parse_codex_review(raw)

    typer.echo(f"\n=== Verdict: {review.verdict} ===")

    # Update handoff metadata with review results
    if result.handoff_file:
        typer.echo(f"→ Review saved to: {result.handoff_file}")

    if issue_number is not None:
        label_result = transition_to_review(issue_number)
        if (
            not label_result.success
            and label_result.error
            and label_result.error != "no_issue_bound"
        ):
            typer.echo(
                f"Warning: Failed to transition issue state: {label_result.error}",
                err=True,
            )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Custom prompt (skips context building)"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
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

    config = VibeConfig.get_defaults()

    gh = GitHubClient()
    pr_data = gh.get_pr(pr_number)
    linked_issues = parse_linked_issues(pr_data.body) if pr_data else []
    issue_number = linked_issues[0] if linked_issues else None

    log.info("Analyzing PR changes")
    scope = ReviewScope.for_pr(pr_number)

    # PR review uses inspect (GitHub API) to fetch PR diff
    inspect_data = run_inspect_json(["pr", str(pr_number)])
    changed_symbols_raw = inspect_data.get("changed_symbols", {})
    changed_symbols = (
        cast(dict[str, list[str]], changed_symbols_raw) if changed_symbols_raw else None
    )

    request = ReviewRequest(scope=scope, changed_symbols=changed_symbols)
    _run_review(
        request,
        config,
        dry_run,
        instructions,
        issue_number=issue_number,
        pr_number=pr_number,
    )


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
    async_mode: _ASYNC_OPT = False,
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

    from vibe3.utils.branch_utils import find_parent_branch
    from vibe3.utils.git_helpers import get_current_branch

    current_branch = get_current_branch()

    if base_branch is None:
        base_branch = find_parent_branch(current_branch)
        if base_branch is None:
            typer.echo(
                "Error: Could not auto-detect parent branch. "
                "Please specify base branch explicitly.",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(f"→ Auto-detected parent branch: {base_branch}")

    flow_service, _ = ensure_flow_for_current_branch()

    if async_mode and not dry_run:
        from vibe3.services.async_execution_service import AsyncExecutionService

        async_svc = AsyncExecutionService()
        command = ["python", "-m", "vibe3", "review", "base", base_branch or ""]
        if instructions:
            command.append(instructions)
        command.append("--no-async")

        async_svc.start_async_execution("reviewer", command, current_branch)
        typer.echo("[green]✓[/] Review started in background")
        typer.echo("Use 'vibe3 flow show' to check status")
        return

    log = logger.bind(
        domain="review",
        action="base",
        current_branch=current_branch,
        base_branch=base_branch,
    )
    log.info("Starting branch review")
    typer.echo(f"→ Review: {current_branch} vs {base_branch}")

    config = VibeConfig.get_defaults()

    flow = flow_service.get_flow_status(current_branch)
    issue_number = flow.task_issue_number if flow else None

    log.info("Analyzing changed files")
    scope = ReviewScope.for_base(base_branch)

    # Build snapshot diff for review context
    structure_diff = build_snapshot_diff(base_branch, current_branch)

    # Get changed symbols from inspect (always needed for function-level impact)
    inspect_data = run_inspect_json(["base", base_branch])
    changed_symbols_raw = inspect_data.get("changed_symbols", {})
    changed_symbols = (
        cast(dict[str, list[str]], changed_symbols_raw) if changed_symbols_raw else None
    )

    # Build request with both snapshot diff and changed symbols
    request = ReviewRequest(
        scope=scope, changed_symbols=changed_symbols, structure_diff=structure_diff
    )
    _run_review(request, config, dry_run, instructions, issue_number=issue_number)
