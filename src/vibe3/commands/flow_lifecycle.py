"""Flow lifecycle commands - blocked."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.common import trace_scope
from vibe3.services.flow_service import FlowService
from vibe3.utils.branch_arg import resolve_branch_arg


def require_flow(service: FlowService, branch: str) -> None:
    """Exit with error if no flow exists for the given branch."""
    if service.get_flow_status(branch):
        return
    typer.echo(
        f"Error: 目标分支 '{branch}' 没有 flow\n"
        "先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支",
        err=True,
    )
    raise typer.Exit(1)


def blocked(
    branch: Annotated[
        str | None, typer.Option("--branch", help="Branch name or issue number")
    ] = None,
    reason: Annotated[
        str | None, typer.Option("--reason", help="Blocking reason")
    ] = None,
    task: Annotated[
        int | None, typer.Option("--task", help="Dependency issue number")
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Mark flow as blocked.

    If --task is provided, automatically adds dependency issue link.

    Examples:
        vibe3 flow blocked --reason "等待外部反馈"
        vibe3 flow blocked --task 218
    """
    if reason is not None and task is not None:
        typer.echo("Error: 不能同时指定 --reason 与 --task", err=True)
        raise typer.Exit(1)

    with trace_scope(trace, "flow blocked", domain="flow"):
        service = FlowService()
        target_branch = resolve_branch_arg(branch)

        logger.bind(
            command="flow blocked",
            branch=target_branch,
            reason=reason,
            task=task,
        ).info("Blocking flow")

        require_flow(service, target_branch)

        service.block_flow(target_branch, reason=reason, blocked_by_issue=task)

        msg = f"Flow blocked on branch '{target_branch}'"
        if reason:
            msg += f": {reason}"
        if task:
            msg += f" (blocked by #{task})"
        typer.echo(msg)


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register flow lifecycle commands."""
    app.command(name="blocked")(blocked)
