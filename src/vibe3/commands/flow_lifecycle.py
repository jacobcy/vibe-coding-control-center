"""Flow lifecycle commands - switch, done, blocked, aborted."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.observability.logger import setup_logging
from vibe3.services.flow_service import FlowService


def switch(
    target: Annotated[str, typer.Argument(help="Flow slug or branch name")],
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Switch to existing flow."""
    if trace:
        setup_logging(verbose=2)

    logger.bind(command="flow switch", target=target).info("Switching to flow")

    service = FlowService()
    flow = service.switch_flow(target)

    if json_output:
        import json

        typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
    else:
        typer.echo(f"Switched to flow '{flow.flow_slug}' on branch '{flow.branch}'")


def done(
    branch: Annotated[str | None, typer.Option("--branch", help="Branch name")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip PR check")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Close flow and delete branch."""
    if trace:
        setup_logging(verbose=2)

    git = GitClient()
    target_branch = branch or git.get_current_branch()

    logger.bind(command="flow done", branch=target_branch, yes=yes).info("Closing flow")

    service = FlowService()
    service.close_flow(target_branch, check_pr=not yes)

    typer.echo(f"Flow closed, branch '{target_branch}' deleted")


def blocked(
    branch: Annotated[str | None, typer.Option("--branch", help="Branch name")] = None,
    reason: Annotated[
        str | None, typer.Option("--reason", help="Blocking reason")
    ] = None,
    by: Annotated[
        int | None, typer.Option("--by", help="Dependency issue number")
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Mark flow as blocked.

    If --by is provided, automatically adds dependency issue link.

    Examples:
        vibe3 flow blocked --reason "等待外部反馈"
        vibe3 flow blocked --by 218
        vibe3 flow blocked --by 218 --reason "需要 #218 先完成"
    """
    if trace:
        setup_logging(verbose=2)

    git = GitClient()
    target_branch = branch or git.get_current_branch()

    logger.bind(
        command="flow blocked",
        branch=target_branch,
        reason=reason,
        by=by,
    ).info("Blocking flow")

    service = FlowService()
    service.block_flow(target_branch, reason=reason, blocked_by_issue=by)

    msg = f"Flow blocked on branch '{target_branch}'"
    if reason:
        msg += f": {reason}"
    if by:
        msg += f" (blocked by #{by})"
    typer.echo(msg)


def aborted(
    branch: Annotated[str | None, typer.Option("--branch", help="Branch name")] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Abort flow and delete branch."""
    if trace:
        setup_logging(verbose=2)

    git = GitClient()
    target_branch = branch or git.get_current_branch()

    logger.bind(command="flow aborted", branch=target_branch).info("Aborting flow")

    service = FlowService()
    service.abort_flow(target_branch)

    typer.echo(f"Flow aborted, branch '{target_branch}' deleted")
