"""Flow binding commands (bind, blocked)."""

import json
import re
from typing import Annotated, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.flow_helpers import _noop
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService


def bind(
    issue: Annotated[str, typer.Argument(help="Issue number (or URL)")],
    role: Annotated[
        Literal["task", "related", "dependency"],
        typer.Option(help="Issue role in flow"),
    ] = "task",
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name (default: current branch)"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Bind a task issue to current flow (flow perspective of task link)."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="flow bind", domain="flow", issue=issue, role=role)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow bind", issue=issue, role=role).info(
            "Binding issue to flow"
        )

        from vibe3.commands.task import parse_issue_ref
        from vibe3.services.task_service import TaskService

        git = GitClient()
        target_branch = branch if branch else git.get_current_branch()

        try:
            issue_number = parse_issue_ref(issue)
        except ValueError:
            match = re.search(r"\d+", issue)
            if not match:
                typer.echo(f"Error: 无法解析 issue: {issue}", err=True)
                raise typer.Exit(1)
            issue_number = int(match.group())

        task_service = TaskService()
        issue_link = task_service.link_issue(target_branch, issue_number, role=role)

        if json_output:
            typer.echo(json.dumps(issue_link.model_dump(), indent=2, default=str))
        else:
            from vibe3.ui.task_ui import render_issue_linked

            render_issue_linked(issue_link)


def blocked(
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name (default: current branch)"),
    ] = None,
    reason: Annotated[
        str | None,
        typer.Option("--reason", help="Blocker description"),
    ] = None,
    by: Annotated[
        int | None,
        typer.Option("--by", help="Dependency issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Mark a flow as blocked.

    If --by is provided, automatically adds dependency issue link.

    Examples:
        vibe3 flow blocked --reason "等待外部反馈"
        vibe3 flow blocked --by 218
        vibe3 flow blocked --by 218 --reason "需要 #218 先完成"
    """
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="flow blocked", domain="flow") if trace else _noop()
    with ctx:
        logger.bind(
            command="flow blocked",
            branch=branch,
            reason=reason,
            blocked_by_issue=by,
        ).info("Blocking flow")

        git = GitClient()
        target_branch = branch if branch else git.get_current_branch()
        service = FlowService()

        try:
            service.block_flow(
                branch=target_branch,
                reason=reason,
                blocked_by_issue=by,
            )

            msg = f"✓ Flow '{target_branch}' marked as blocked"
            if reason:
                msg += f": {reason}"
            typer.echo(msg)

        except Exception as e:
            if isinstance(e, Exception) and e.__class__.__name__ == "UserError":
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)
            raise
