"""Review command - 代码审核层,基于 inspect 提供的上下文调用 Codex."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.review_helpers import call_codex, run_inspect_json
from vibe3.models.change_source import (
    BranchSource,
    CommitSource,
    PRSource,
    UncommittedSource,
)
from vibe3.services.context_builder import build_review_context
from vibe3.services.review_parser import convert_to_github_format, parse_codex_review
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="review",
    help="Code review using Codex",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]
_PUBLISH_OPT = Annotated[
    bool, typer.Option("--publish", help="Post review comments to GitHub")
]


@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    trace: _TRACE_OPT = False,
    publish: _PUBLISH_OPT = False,
) -> None:
    """Review a PR (calls inspect pr internally for context).

    Example: vibe review pr 42
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="pr", pr_number=pr_number)
    log.info("Starting PR review")

    # 1. 获取 inspect 分析结果
    inspect_data = run_inspect_json(["pr", str(pr_number)])

    # 2. 获取 diff
    from vibe3.clients.github_client import GitHubClient

    git = GitClient(github_client=GitHubClient())
    diff = git.get_diff(PRSource(pr_number=pr_number))

    # 3. 构建上下文
    context = build_review_context(
        diff=diff,
        impact=json.dumps(inspect_data.get("impact"), indent=2),
        dag=json.dumps(inspect_data.get("dag"), indent=2),
        score=json.dumps(inspect_data.get("score"), indent=2),
    )

    # 4. 调用 Codex
    raw = call_codex(context)
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    # 5. 发布到 GitHub（含行级 comments + Merge Gate）
    if publish:
        from vibe3.clients.github_client import GitHubClient

        gh = GitHubClient()

        # 7.1 行级 comments 发布
        github_comments = convert_to_github_format(review) if review.comments else []
        event = (
            "REQUEST_CHANGES"
            if review.verdict == "BLOCK"
            else "APPROVE" if review.verdict == "PASS" else "COMMENT"
        )
        summary = (
            f"**Automated Review** — Risk score: "
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
            dismiss_previous=True,  # 避免重复 review
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
def uncommitted(
    trace: _TRACE_OPT = False,
) -> None:
    """Review uncommitted changes.

    Example: vibe review --uncommitted
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="uncommitted")
    log.info("Reviewing uncommitted changes")

    git = GitClient()
    diff = git.get_diff(UncommittedSource())

    if not diff.strip():
        typer.echo("No uncommitted changes found.")
        return

    context = build_review_context(diff=diff)
    raw = call_codex(context)
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)


@app.command()
def base(
    branch: Annotated[str, typer.Argument(help="Branch to review against main")],
    trace: _TRACE_OPT = False,
    publish: _PUBLISH_OPT = False,
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

    raw = call_codex(context)
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)


@app.command()
def commit(
    sha: Annotated[str, typer.Argument(help="Commit SHA")],
    trace: _TRACE_OPT = False,
) -> None:
    """Review a specific commit.

    Example: vibe review commit HEAD~1
    """
    if trace:
        enable_trace()

    log = logger.bind(domain="review", action="commit", sha=sha)
    log.info("Reviewing commit")

    inspect_data = run_inspect_json(["commit", sha])

    git = GitClient()
    diff = git.get_diff(CommitSource(sha=sha))

    context = build_review_context(
        diff=diff,
        impact=json.dumps(inspect_data.get("impact"), indent=2),
        dag=json.dumps(inspect_data.get("dag"), indent=2),
        score=json.dumps(inspect_data.get("score"), indent=2),
    )

    raw = call_codex(context)
    review = parse_codex_review(raw)

    typer.echo(raw)
    typer.echo(
        f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
    )

    if review.verdict == "BLOCK":
        raise typer.Exit(1)


@app.command("analyze-commit")
def analyze_commit_cmd(
    sha: Annotated[str, typer.Argument(help="Commit SHA (e.g. HEAD, abc123)")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Analyze commit complexity to determine if review should be triggered.

    Example: vibe review analyze-commit HEAD
    """
    from vibe3.services.commit_analyzer import analyze_commit, analyze_commit_json

    log = logger.bind(domain="review", action="analyze_commit", sha=sha)
    log.info("Analyzing commit complexity")

    if as_json:
        typer.echo(analyze_commit_json(sha))
    else:
        result = analyze_commit(sha)
        typer.echo(f"Lines changed:    {result['lines_changed']}")
        typer.echo(f"Files changed:    {result['files_changed']}")
        typer.echo(f"Complexity score: {result['complexity_score']}/10")
        typer.echo(f"Should review:    {result['should_review']}")
