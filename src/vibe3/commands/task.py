#!/usr/bin/env python3
"""Task command handlers."""

import json
import re
from contextlib import contextmanager
from typing import Annotated, Iterator, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.task_service import TaskService
from vibe3.ui.task_ui import render_issue_linked

app = typer.Typer(
    help="Manage execution tasks", no_args_is_help=True, rich_markup_mode="rich"
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def parse_issue_url(issue_url: str) -> int:
    """Parse issue number from GitHub URL or plain number.

    Args:
        issue_url: GitHub issue URL or issue number string

    Returns:
        Issue number

    Raises:
        ValueError: If the URL/number is invalid
    """
    if issue_url.isdigit():
        return int(issue_url)

    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", issue_url)
    if match:
        return int(match.group(1))

    raise ValueError(f"Invalid issue URL or number: {issue_url}")


@app.command()
def list(
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """List all tasks."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="task list", domain="task") if trace else _noop()
    with ctx:
        logger.bind(command="task list").info("Listing tasks")

        git = GitClient()
        service = TaskService()
        branch = git.get_current_branch()
        task = service.get_task(branch)

        if not task:
            logger.info("No tasks found on current branch")
            typer.echo("No tasks found")
            return

        if json_output:
            typer.echo(json.dumps(task.model_dump(), indent=2, default=str))
        else:
            typer.echo(f"Branch: {task.branch}")
            if task.task_issue_number:
                typer.echo(f"Task Issue: #{task.task_issue_number}")
            typer.echo(f"Status: {task.flow_status}")


@app.command()
def show(
    task_id: Annotated[str, typer.Argument(help="Branch name or task ID")],
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Show task details."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="task show", domain="task", task_id=task_id)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="task show", task_id=task_id).info("Showing task details")

        service = TaskService()
        task = service.get_task(task_id)

        if not task:
            logger.error(f"Task not found: {task_id}")
            typer.echo(f"Task not found: {task_id}", err=True)
            raise typer.Exit(1)

        if json_output:
            typer.echo(json.dumps(task.model_dump(), indent=2, default=str))
        else:
            typer.echo(f"Branch: {task.branch}")
            if task.task_issue_number:
                typer.echo(f"Task Issue: #{task.task_issue_number}")
            typer.echo(f"Status: {task.flow_status}")
            if task.next_step:
                typer.echo(f"Next Step: {task.next_step}")


@app.command()
def link(
    issue_url: Annotated[str, typer.Argument(help="Issue URL or number")],
    role: Annotated[
        Literal["task", "related"], typer.Option(help="Issue role")
    ] = "related",
    actor: Annotated[str, typer.Option(help="Actor linking the issue")] = "unknown",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Link an issue to current flow."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="task link", domain="task") if trace else _noop()
    with ctx:
        logger.bind(
            command="task link", issue_url=issue_url, role=role, actor=actor
        ).info("Linking issue to flow")

        try:
            issue_number = parse_issue_url(issue_url)
            git = GitClient()
            branch = git.get_current_branch()
            service = TaskService()
            issue_link = service.link_issue(branch, issue_number, role, actor)

            if json_output:
                typer.echo(json.dumps(issue_link.model_dump(), indent=2, default=str))
            else:
                render_issue_linked(issue_link)

        except ValueError as e:
            logger.error(f"Invalid issue reference: {e}")
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
