"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated

import typer
from loguru import logger

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
_AGENT_OPT = Annotated[
    str,
    typer.Option(
        "--agent",
        help="Agent preset from ~/.codeagent/models.json (e.g., code-reviewer)",
    ),
]
_MODEL_OPT = Annotated[
    str | None, typer.Option("--model", help="Model override for codeagent-wrapper")
]


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    trace: _TRACE_OPT = False,
    agent: _AGENT_OPT = "code-reviewer",
    model: _MODEL_OPT = None,
) -> None:
    """Review a PR locally (generates review output, does not publish to GitHub).

    This command is for local review only. To publish review to GitHub,
    use `pr ready` command instead.

    Example: vibe review pr 42
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="pr", pr_number=pr_number)
    log.info("Starting local PR review")

    # Build context (just policy and format - reviewer runs git diff themselves)
    context = build_review_context()

    # Call agent via codeagent-wrapper
    options = ReviewAgentOptions(
        agent=agent,
        model=model,
    )
    result = run_review_agent(context, options)
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
    agent: _AGENT_OPT = "code-reviewer",
    model: _MODEL_OPT = None,
) -> None:
    """Review current branch changes relative to base branch.

    By default, compares current branch against origin/main (recommended for projects
    that don't develop on main branch locally).

    Examples:
        vibe review base                 # Compare current branch vs origin/main
        vibe review base origin/develop  # Compare current branch vs origin/develop
        vibe review base main            # Compare current branch vs local main
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

    # Build context (just policy and format - reviewer runs git diff themselves)
    context = build_review_context()

    # Call agent via codeagent-wrapper
    options = ReviewAgentOptions(
        agent=agent,
        model=model,
    )
    result = run_review_agent(context, options)
    raw = result.stdout
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)
