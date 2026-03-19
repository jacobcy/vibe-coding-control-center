"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated, cast

import typer
from loguru import logger

from vibe3.commands.review_helpers import run_inspect_json
from vibe3.config.settings import VibeConfig
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


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
) -> None:
    """Review a PR locally (generates review output, does not publish to GitHub).

    This command is for local review only. To publish review to GitHub,
    use `pr ready` command instead.

    Example: vibe review pr 42
    Example: vibe review pr 42 --dry-run  # Print command and prompt only
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="pr", pr_number=pr_number)
    log.info("Starting local PR review")

    # Load config
    config = VibeConfig.get_defaults()

    # Get AST-level analysis (changed functions, not file lists)
    inspect_data = run_inspect_json(["pr", str(pr_number)])
    changed_symbols_raw = inspect_data.get("changed_symbols", {})
    changed_symbols = (
        cast(dict[str, list[str]], changed_symbols_raw) if changed_symbols_raw else None
    )

    # Build context with AST analysis
    context = build_review_context(
        changed_symbols=changed_symbols,
        config=config,
    )

    # Call agent via codeagent-wrapper
    options = ReviewAgentOptions(
        agent=config.review.agent_config.agent,
        backend=config.review.agent_config.backend,
        model=config.review.agent_config.model,
    )
    result = run_review_agent(context, options, dry_run=dry_run)

    if dry_run:
        return

    raw = result.stdout
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)


@app.command()
def base(
    base_branch: Annotated[
        str,
        typer.Argument(help="Base branch to compare against (default: origin/main)"),
    ] = "origin/main",
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
) -> None:
    """Review current branch changes relative to base branch.

    By default, compares current branch against origin/main (recommended for projects
    that don't develop on main branch locally).

    Examples:
        vibe review base                 # Compare current branch vs origin/main
        vibe review base origin/develop  # Compare current branch vs origin/develop
        vibe review base main            # Compare current branch vs local main
        vibe review base --dry-run       # Print command and prompt only
    """
    if trace:
        enable_trace()

    from vibe3.utils.git_helpers import get_current_branch

    current_branch = get_current_branch()

    log = logger.bind(
        domain="review",
        action="base",
        current_branch=current_branch,
        base_branch=base_branch,
    )
    log.info("Reviewing branch changes")

    # Load config
    config = VibeConfig.get_defaults()

    # Get AST-level analysis (changed functions, not file lists)
    inspect_data = run_inspect_json(["base", base_branch])
    changed_symbols_raw = inspect_data.get("changed_symbols", {})
    changed_symbols = (
        cast(dict[str, list[str]], changed_symbols_raw) if changed_symbols_raw else None
    )

    # Build context with AST analysis
    context = build_review_context(
        changed_symbols=changed_symbols,
        config=config,
    )

    # Call agent via codeagent-wrapper
    options = ReviewAgentOptions(
        agent=config.review.agent_config.agent,
        backend=config.review.agent_config.backend,
        model=config.review.agent_config.model,
    )
    result = run_review_agent(context, options, dry_run=dry_run)

    if dry_run:
        return

    raw = result.stdout
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)
