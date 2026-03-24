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
from vibe3.services.context_builder import build_review_context
from vibe3.services.label_integration import transition_to_review
from vibe3.services.review_parser import ParsedReview, parse_codex_review
from vibe3.services.review_runner import (
    ReviewAgentOptions,
    format_agent_actor,
    run_review_agent,
)
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="review",
    help="Code review using inspect context and codeagent-wrapper",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]
_DRY_RUN_OPT = Annotated[
    bool,
    typer.Option("--dry-run", help="Print command and prompt without executing"),
]
_MESSAGE_OPT = Annotated[
    Optional[str],
    typer.Option("--message", "-m", help="Custom prompt (skips context building)"),
]


def _record_review_event(
    review: ParsedReview,
    actor: str,
    review_content: str | None = None,
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

    store.add_event(
        branch,
        "handoff_review",
        actor,
        detail=f"Verdict: {review.verdict}, {len(review.comments)} comments",
        refs={"ref": str(review_file), "verdict": review.verdict},
    )
    store.update_flow_state(branch, reviewer_actor=actor, audit_ref=str(review_file))

    return review_file


def _run_review(
    request: ReviewRequest,
    config: VibeConfig,
    dry_run: bool,
    message: str | None,
    issue_number: int | None = None,
) -> None:
    log = logger.bind(domain="review", scope=request.scope.kind)

    log.info("Building review context")
    prompt_file_content = build_review_context(request, config)

    task = None
    if message:
        task = message
        log.info("Using custom task message")
        typer.echo(f"→ Custom task: {message[:60]}{'...' if len(message) > 60 else ''}")
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
    )
    typer.echo("→ Running review...")
    options = ReviewAgentOptions(
        agent=config.review.agent_config.agent,
        backend=config.review.agent_config.backend,
        model=config.review.agent_config.model,
    )
    result = run_review_agent(prompt_file_content, options, task=task, dry_run=dry_run)

    if dry_run:
        return

    raw = result.stdout
    review = parse_codex_review(raw)

    typer.echo(f"\n=== Verdict: {review.verdict} ===")

    review_file = _record_review_event(
        review,
        actor=format_agent_actor(options),
        review_content=raw,
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
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    message: _MESSAGE_OPT = None,
) -> None:
    """Review a PR locally (generates review output, does not publish to GitHub)."""
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
    _run_review(request, config, dry_run, message, issue_number=issue_number)


@app.command()
def base(
    base_branch: Annotated[
        str,
        typer.Argument(help="Base branch to compare against (default: origin/main)"),
    ] = "origin/main",
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    message: _MESSAGE_OPT = None,
) -> None:
    """Review current branch changes relative to base branch."""
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
    structure_diff = build_snapshot_diff(base_branch)

    # Get changed symbols from inspect (always needed for function-level impact)
    inspect_data = run_inspect_json(["base", base_branch])
    changed_symbols_raw = inspect_data.get("changed_symbols", {})
    changed_symbols = (
        cast(dict[str, list[str]], changed_symbols_raw) if changed_symbols_raw else None
    )

    # Build request with both snapshot diff and changed symbols
    request = ReviewRequest(
        scope=scope,
        changed_symbols=changed_symbols,
        structure_diff=structure_diff,
    )

    _run_review(request, config, dry_run, message, issue_number=issue_number)
