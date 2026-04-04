#!/usr/bin/env python3
"""Task command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Any, Iterator

import typer

from vibe3.clients.github_client import GitHubClient
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.milestone_service import MilestoneService
from vibe3.services.task_service import TaskService
from vibe3.services.task_usecase import TaskUsecase
from vibe3.ui.task_ui import (
    render_task_show_with_milestone,
)

app = typer.Typer(
    help="Manage execution tasks", no_args_is_help=True, rich_markup_mode="rich"
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _build_task_usecase() -> TaskUsecase:
    """Construct a task usecase with command-local service wiring."""
    return TaskUsecase(
        flow_service=FlowService(),
        task_service=TaskService(),
    )


def _build_milestone_service() -> MilestoneService:
    """Construct a milestone service."""
    return MilestoneService()


def _is_human_comment(comment: dict[str, Any]) -> bool:
    author = comment.get("author") or {}
    login = str(author.get("login") or "").strip().lower()
    if not login:
        return True
    if login == "linear" or login.endswith("[bot]"):
        return False
    return True


def _render_comments(issue: dict[str, Any], json_output: bool) -> None | dict:
    comments = issue.get("comments") or []
    latest_comment = comments[-1] if comments else None
    latest_human = next(
        (comment for comment in reversed(comments) if _is_human_comment(comment)),
        None,
    )

    if json_output:
        return {
            "issue": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "labels": [label.get("name") for label in issue.get("labels", [])],
            "latest_comment": latest_comment,
            "latest_human_comment": latest_human,
        }

    typer.echo("\nLatest Comment:")
    if latest_comment:
        author = (latest_comment.get("author") or {}).get("login") or "unknown"
        typer.echo(f"  author  {author}")
        typer.echo(f"  body    {str(latest_comment.get('body') or '').strip()}")
    else:
        typer.echo("  (no comments)")

    typer.echo("\nLatest Human Instruction:")
    if latest_human:
        author = (latest_human.get("author") or {}).get("login") or "unknown"
        typer.echo(f"  author  {author}")
        typer.echo(f"  body    {str(latest_human.get('body') or '').strip()}")
    else:
        typer.echo("  (no human comments)")

    return None


@app.command()
def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    comments: Annotated[
        bool, typer.Option("--comments", help="Include latest issue comments context")
    ] = False,
) -> None:
    """Show task details."""
    usecase = _build_task_usecase()
    milestone_svc = _build_milestone_service()

    try:
        target_branch = usecase.resolve_branch(branch)
    except RuntimeError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="task show", domain="task", branch=target_branch)
        if trace
        else _noop()
    )
    with ctx:
        task_result = usecase.show_task(target_branch)

        # Fetch milestone context if task has an issue number
        milestone_ctx = None
        issue_number = None
        if task_result.local_task and task_result.local_task.task_issue_number:
            issue_number = task_result.local_task.task_issue_number

        if issue_number:
            milestone_ctx = milestone_svc.get_milestone_context(issue_number)

        # Delegate rendering to UI layer
        render_task_show_with_milestone(task_result, milestone_ctx, json_output)

        if comments and issue_number:
            issue = GitHubClient().view_issue(issue_number)
            if issue == "network_error":
                typer.echo("\nIssue comments unavailable: network/auth error")
            elif issue is None:
                typer.echo(
                    f"\nIssue comments unavailable: issue #{issue_number} not found"
                )
            else:
                assert isinstance(issue, dict)
                comments_data = _render_comments(issue, json_output)
                if json_output and comments_data and task_result.local_task:
                    # Merge comments into a single JSON with task data
                    combined = task_result.local_task.model_dump()
                    combined["comments"] = comments_data
                    typer.echo(json.dumps(combined, indent=2, default=str))
                elif not json_output:
                    pass  # _render_comments already printed text
                elif task_result.local_task:
                    pass  # task JSON already printed; comments_data is just info


@app.command()
def status(
    all_flows: Annotated[
        bool,
        typer.Option("--all", help="显示所有状态的 flow（含 done/aborted/stale）"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Show task-oriented global status dashboard."""
    from vibe3.commands import status as status_command

    status_command.status(
        all_flows=all_flows,
        json_output=json_output,
        trace=trace,
    )
