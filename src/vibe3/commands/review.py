"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated, Optional, cast

import typer
from loguru import logger

from vibe3.commands.review_helpers import run_inspect_json
from vibe3.config.settings import VibeConfig
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.services.context_builder import build_review_context
from vibe3.services.review_parser import parse_codex_review
from vibe3.services.review_runner import ReviewAgentOptions, run_review_agent
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


def _run_review(
    request: ReviewRequest, config: VibeConfig, dry_run: bool, message: str | None
) -> None:
    """Execute review for a given request.

    This is the shared logic for both base and pr commands.

    Args:
        request: Review request with scope and symbols
        config: Configuration instance
        dry_run: If True, print command without executing
        message: Optional custom task message
    """
    log = logger.bind(domain="review", scope=request.scope.kind)

    log.info("Building review context")
    prompt_file_content = build_review_context(request, config)

    # Determine task: custom message, config default, or None
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

    # Call agent via codeagent-wrapper
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

    if review.verdict == "BLOCK":
        raise typer.Exit(1)


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    message: _MESSAGE_OPT = None,
) -> None:
    """Review a PR locally (generates review output, does not publish to GitHub).

    This command is for local review only. To publish review to GitHub,
    use `pr ready` command instead.

    Examples:
        vibe review pr 42
        vibe review pr 42 --dry-run  # Print command and prompt only
        vibe review pr 42 -m "Focus on security issues"  # Custom prompt
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="pr", pr_number=pr_number)
    log.info("Starting PR review")
    typer.echo(f"→ Review: PR #{pr_number}")

    # Load config
    config = VibeConfig.get_defaults()

    # Create scope and get inspect data
    log.info("Analyzing PR changes")
    scope = ReviewScope.for_pr(pr_number)
    inspect_data = run_inspect_json(["pr", str(pr_number)])
    changed_symbols_raw = inspect_data.get("changed_symbols", {})
    changed_symbols = (
        cast(dict[str, list[str]], changed_symbols_raw) if changed_symbols_raw else None
    )

    # Build request and execute review
    request = ReviewRequest(scope=scope, changed_symbols=changed_symbols)
    _run_review(request, config, dry_run, message)


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
    """Review current branch changes relative to base branch.

    By default, compares current branch against origin/main (recommended for projects
    that don't develop on main branch locally).

    Examples:
        vibe review base                 # Compare current branch vs origin/main
        vibe review base origin/develop  # Compare current branch vs origin/develop
        vibe review base main            # Compare current branch vs local main
        vibe review base --dry-run       # Print command and prompt only
        vibe review base -m "Focus on security"  # Custom task
    """
    if trace:
        enable_trace()

    from vibe3.utils.git_helpers import get_current_branch

    # Note: base branch validation is handled by inspect_base command
    # which is called by run_inspect_json below

    current_branch = get_current_branch()

    log = logger.bind(
        domain="review",
        action="base",
        current_branch=current_branch,
        base_branch=base_branch,
    )
    log.info("Starting branch review")
    typer.echo(f"→ Review: {current_branch} vs {base_branch}")

    # Load config
    config = VibeConfig.get_defaults()

    # Create scope and get inspect data
    log.info("Analyzing changed files")
    scope = ReviewScope.for_base(base_branch)
    inspect_data = run_inspect_json(["base", base_branch])
    changed_symbols_raw = inspect_data.get("changed_symbols", {})
    changed_symbols = (
        cast(dict[str, list[str]], changed_symbols_raw) if changed_symbols_raw else None
    )

    # Build request and execute review
    request = ReviewRequest(scope=scope, changed_symbols=changed_symbols)
    _run_review(request, config, dry_run, message)
