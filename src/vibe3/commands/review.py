"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional, cast

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.review_helpers import build_snapshot_diff, run_inspect_json
from vibe3.config.settings import VibeConfig
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.models.review_runner import ReviewAgentOptions
from vibe3.services.context_builder import build_review_context
from vibe3.services.label_integration import transition_to_review
from vibe3.services.review_parser import ParsedReview, parse_codex_review
from vibe3.services.review_runner import format_agent_actor, run_review_agent
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="review",
    help="Code review with two modes:\n\n"
    "  pr <number>  - Review existing PR from GitHub (analyzes PR diff)\n"
    "  base [branch] - Review local changes vs base branch (compares snapshots)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]
_DRY_RUN_OPT = Annotated[
    bool, typer.Option("--dry-run", help="Print command and prompt without executing")
]


def _record_review_event(
    review: ParsedReview,
    actor: str,
    review_content: str | None = None,
    session_id: str | None = None,
) -> Path | None:
    """Record review to handoff."""
    store = SQLiteClient()
    git = GitClient()
    try:
        branch = git.get_current_branch()
    except Exception:
        return None

    git_dir = git.get_git_common_dir()
    handoff_dir = get_branch_handoff_dir(git_dir, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    review_file = handoff_dir / f"review-{timestamp}.md"

    if review_content:
        review_file.write_text(review_content, encoding="utf-8")

    refs: dict[str, str] = {"ref": str(review_file), "verdict": review.verdict}
    if session_id:
        refs["session_id"] = session_id

    store.add_event(
        branch,
        "handoff_review",
        actor,
        detail=f"Verdict: {review.verdict}, {len(review.comments)} comments",
        refs=refs,
    )
    store.update_flow_state(
        branch,
        reviewer_actor=actor,
        audit_ref=str(review_file),
        reviewer_session_id=session_id,
    )

    return review_file


def _run_review(
    request: ReviewRequest,
    config: VibeConfig,
    dry_run: bool,
    instructions: str | None,
    issue_number: int | None = None,
    pr_number: int | None = None,
) -> None:
    from vibe3.services.flow_service import FlowService

    log = logger.bind(domain="review", scope=request.scope.kind)

    # Load existing session_id if available
    git = GitClient()
    try:
        branch = git.get_current_branch()
        flow_status = FlowService().get_flow_status(branch)
        session_id = flow_status.reviewer_session_id if flow_status else None
    except Exception:
        session_id = None

    log.info("Building review context")
    prompt_file_content = build_review_context(request, config)

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

    log.info(
        "Running review agent",
        agent=config.review.agent_config.agent,
        backend=config.review.agent_config.backend,
        model=config.review.agent_config.model,
        session_id=session_id,
    )
    typer.echo("→ Running review...")
    options = ReviewAgentOptions(
        agent=config.review.agent_config.agent,
        backend=config.review.agent_config.backend,
        model=config.review.agent_config.model,
    )
    result = run_review_agent(
        prompt_file_content, options, task=task, dry_run=dry_run, session_id=session_id
    )

    if dry_run:
        return

    raw = result.stdout
    review = parse_codex_review(raw)

    typer.echo(f"\n=== Verdict: {review.verdict} ===")

    effective_session_id = result.session_id or session_id
    review_file = _record_review_event(
        review,
        actor=format_agent_actor(options),
        review_content=raw,
        session_id=effective_session_id,
    )
    if review_file:
        typer.echo(f"→ Review saved to: {review_file}")

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
        str,
        typer.Argument(help="Base branch to compare against (default: origin/main)"),
    ] = "origin/main",
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Custom prompt (skips context building)"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
) -> None:
    """Review local branch changes against a base branch (compares codebase snapshots).

    This command compares your current local branch state against a base branch.
    It analyzes:
    - Structure diff (file/module/dependency changes)
    - Changed symbols (function-level impact)
    - Impacted modules (DAG upstream dependencies)

    Use this to review local changes before pushing or creating a PR.

    Example: vibe3 review base origin/main "Focus on behavior changes"
    """
    if trace:
        enable_trace()

    from vibe3.services.flow_service import FlowService
    from vibe3.utils.git_helpers import get_current_branch

    current_branch = get_current_branch()

    log = logger.bind(
        domain="review",
        action="base",
        current_branch=current_branch,
        base_branch=base_branch,
    )
    log.info("Starting branch review")
    typer.echo(f"→ Review: {current_branch} vs {base_branch}")

    config = VibeConfig.get_defaults()

    flow = FlowService().get_flow_status(current_branch)
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
