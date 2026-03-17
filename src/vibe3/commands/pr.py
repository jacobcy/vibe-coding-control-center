#!/usr/bin/env python3
"""PR command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator

import typer
from loguru import logger

from vibe3.models.pr import PRMetadata
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import (
    render_pr_created,
    render_pr_details,
    render_pr_merged,
    render_pr_ready,
    render_pr_review,
    render_version_bump,
)

app = typer.Typer(help="Manage Pull Requests")


@contextmanager
def _noop() -> Iterator[None]:
    """空上下文管理器，用于 trace=False 时的占位."""
    yield


@app.command()
def draft(
    title: Annotated[str, typer.Option("-t", help="PR title")],
    body: Annotated[str, typer.Option("-b", help="PR description")] = "",
    base: Annotated[str, typer.Option(help="Base branch")] = "main",
    task: Annotated[int | None, typer.Option(help="Task issue #")] = None,
    flow: Annotated[str | None, typer.Option(help="Flow slug")] = None,
    spec: Annotated[str | None, typer.Option(help="Spec reference")] = None,
    planner: Annotated[str | None, typer.Option(help="Planner agent")] = None,
    executor: Annotated[str | None, typer.Option(help="Executor agent")] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Create draft PR."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="pr draft", domain="pr", title=title)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="pr draft", title=title, base=base).info(
            "Creating draft PR"
        )

        service = PRService()
        metadata = None
        if any([task, flow, spec, planner, executor]):
            metadata = PRMetadata(
                task_issue=task,
                flow_slug=flow,
                spec_ref=spec,
                planner=planner,
                executor=executor,
            )
        pr = service.create_draft_pr(
            title=title, body=body, base_branch=base, metadata=metadata
        )

        if json_output:
            typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
        else:
            render_pr_created(pr)


@app.command()
def show(
    pr_number: Annotated[int | None, typer.Argument(help="PR number")] = None,
    branch: Annotated[str | None, typer.Option("-b", help="Branch name")] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Show PR details."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="pr show", domain="pr") if trace else _noop()
    with ctx:
        logger.bind(command="pr show", pr_number=pr_number, branch=branch).info(
            "Fetching PR details"
        )

        service = PRService()
        pr = service.get_pr(pr_number, branch)

        if not pr:
            logger.error("PR not found")
            raise typer.Exit(1)

        if json_output:
            typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
        else:
            render_pr_details(pr)


@app.command()
def ready(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="自动确认（跳过交互）")
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Mark PR as ready for review."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="pr ready", domain="pr", pr_number=pr_number)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="pr ready", pr_number=pr_number).info(
            "Marking PR as ready for review"
        )

        if not yes:
            confirmed = typer.confirm(
                "Mark PR #"
                f"{pr_number} as ready for review? (draft → ready, irreversible)"
            )
            if not confirmed:
                logger.info("Aborted by user")
                raise typer.Exit(0)

        service = PRService()
        pr = service.mark_ready(pr_number)

        if json_output:
            typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
        else:
            render_pr_ready(pr)


@app.command()
def merge(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="自动确认（跳过交互）")
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Merge PR."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="pr merge", domain="pr", pr_number=pr_number)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="pr merge", pr_number=pr_number).info("Merging PR")

        if not yes:
            confirmed = typer.confirm(f"Merge PR #{pr_number}? (irreversible)")
            if not confirmed:
                logger.info("Aborted by user")
                raise typer.Exit(0)

        service = PRService()
        pr = service.merge_pr(pr_number)

        if json_output:
            typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
        else:
            render_pr_merged(pr)


@app.command()
def version_bump(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    group: Annotated[str | None, typer.Option("-g", help="Task group")] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Calculate version bump for PR."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="pr version-bump", domain="pr", pr_number=pr_number)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="pr version-bump", pr_number=pr_number, group=group).info(
            "Calculating version bump"
        )

        service = PRService()
        response = service.calculate_version_bump(pr_number, group)

        if json_output:
            typer.echo(json.dumps(response.model_dump(), indent=2, default=str))
        else:
            render_version_bump(response)


@app.command()
def review(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    publish: Annotated[bool, typer.Option(help="Publish review as comment")] = True,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Review PR using local LLM (codex)."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="pr review", domain="pr", pr_number=pr_number)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="pr review", pr_number=pr_number, publish=publish).info(
            "Reviewing PR"
        )

        service = PRService()
        response = service.review_pr(pr_number, publish)

        if json_output:
            typer.echo(json.dumps(response.model_dump(), indent=2, default=str))
        else:
            render_pr_review(response)
