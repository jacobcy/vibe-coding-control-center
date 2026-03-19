"""Review command - Code review layer using inspect context and codeagent-wrapper."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.review_helpers import run_inspect_json
from vibe3.models.change_source import BranchSource, PRSource
from vibe3.services.context_builder import build_review_context
from vibe3.services.review_parser import convert_to_github_format, parse_codex_review
from vibe3.services.review_runner import AgentType, ReviewAgentOptions, run_review_agent
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
_PUBLISH_OPT = Annotated[
    bool, typer.Option("--publish", help="Post review comments to GitHub")
]
_AGENT_OPT = Annotated[
    str, typer.Option("--agent", help="Agent preset for codeagent-wrapper")
]
_MODEL_OPT = Annotated[
    str | None, typer.Option("--model", help="Model override for codeagent-wrapper")
]


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    trace: _TRACE_OPT = False,
    publish: _PUBLISH_OPT = False,
    agent: _AGENT_OPT = "codex",
    model: _MODEL_OPT = None,
) -> None:
    """Review a PR (calls inspect pr internally for context).

    Example: vibe review pr 42
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="pr", pr_number=pr_number)
    log.info("Starting PR review")

    # 1. Get inspect analysis result
    inspect_data = run_inspect_json(["pr", str(pr_number)])

    # 2. Get diff
    from vibe3.clients.github_client import GitHubClient

    git = GitClient(github_client=GitHubClient())
    diff = git.get_diff(PRSource(pr_number=pr_number))

    # 3. Build context
    context = build_review_context(
        diff=diff,
        impact=json.dumps(inspect_data.get("impact"), indent=2),
        dag=json.dumps(inspect_data.get("dag"), indent=2),
        score=json.dumps(inspect_data.get("score"), indent=2),
    )

    # 4. Call agent via codeagent-wrapper
    options = ReviewAgentOptions(
        agent=AgentType(agent),
        model=model,
    )
    result = run_review_agent(context, options)
    raw = result.stdout
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    # 5. Publish to GitHub (with line-level comments + Merge Gate)
    if publish:
        from vibe3.clients.github_client import GitHubClient

        gh = GitHubClient()

        # 7.1 Line-level comments publishing
        github_comments = convert_to_github_format(review) if review.comments else []
        event = (
            "REQUEST_CHANGES"
            if review.verdict == "BLOCK"
            else "APPROVE" if review.verdict == "PASS" else "COMMENT"
        )
        summary = (
            f"**Automated Review** -- Risk score: "
            f"{inspect_data.get('score', {}).get('score', '?')}\n\n"  # type: ignore
            f"Verdict: **{review.verdict}**"
        )

        log.bind(event=event, comment_count=len(github_comments)).info(
            "Publishing review to GitHub"
        )
        gh.create_review(
            pr_number,
            body=summary,
            event=event,
            comments=github_comments if github_comments else None,
            dismiss_previous=True,  # Avoid duplicate reviews
        )
        log.success("Review published to GitHub")

        # 7.2 Merge Gate
        risk_level = str(inspect_data.get("score", {}).get("risk_level", "LOW"))  # type: ignore
        sha = gh.get_pr_head_sha(pr_number)
        log.bind(risk_level=risk_level).info("Setting commit status")
        if risk_level == "CRITICAL":
            gh.create_commit_status(
                sha,
                state="failure",
                description="CRITICAL risk score - review required",
            )
        else:
            gh.create_commit_status(
                sha,
                state="success",
                description=f"{risk_level} risk score",
            )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)


@app.command()
def base(
    branch: Annotated[str, typer.Argument(help="Branch to review against main")],
    trace: _TRACE_OPT = False,
    publish: _PUBLISH_OPT = False,
    agent: _AGENT_OPT = "codex",
    model: _MODEL_OPT = None,
) -> None:
    """Review branch changes relative to main.

    Example: vibe review base feature/my-branch
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="base", branch=branch)
    log.info("Reviewing branch changes")

    inspect_data = run_inspect_json(["base", branch])

    git = GitClient()
    diff = git.get_diff(BranchSource(branch=branch))

    context = build_review_context(
        diff=diff,
        impact=json.dumps(inspect_data.get("impact"), indent=2),
        dag=json.dumps(inspect_data.get("dag"), indent=2),
        score=json.dumps(inspect_data.get("score"), indent=2),
    )

    # Call agent via codeagent-wrapper
    options = ReviewAgentOptions(
        agent=AgentType(agent),
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
