"""Flow lifecycle commands - switch, done, blocked, aborted."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.common import trace_scope
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_service import PRService


def resolve_pr_to_branch(pr: int) -> str:
    """Resolve a PR number to its head branch name.

    Returns the head branch name, or exits on error.
    """
    pr_data = PRService().get_pr(pr_number=pr)
    if pr_data is None:
        typer.echo(f"Error: 未找到 PR #{pr}", err=True)
        raise typer.Exit(1)
    return pr_data.head_branch


def validate_mutually_exclusive_branch_pr(branch: str | None, pr: int | None) -> None:
    """Ensure --branch and --pr are not both specified."""
    if branch is not None and pr is not None:
        typer.echo("Error: 不能同时指定 --branch 与 --pr", err=True)
        raise typer.Exit(1)


def resolve_target_branch(branch: str | None, pr: int | None) -> str | None:
    """Resolve target branch from --branch, --pr, or None.

    Returns None when neither option is provided (caller should fallback
    to current branch).
    """
    validate_mutually_exclusive_branch_pr(branch, pr)
    if pr is not None:
        return resolve_pr_to_branch(pr)
    return branch


def switch(
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name or flow slug to switch to"),
    ] = None,
    pr: Annotated[
        int | None,
        typer.Option("--pr", help="PR number to resolve head branch from"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Switch to existing flow."""
    target = resolve_target_branch(branch, pr)

    if target is None:
        typer.echo(
            "Error: 必须指定目标分支/flow slug，或指定 PR 号\n"
            "使用: vibe3 flow switch --branch <branch-or-slug>\n"
            "  或: vibe3 flow switch --pr <pr-number>",
            err=True,
        )
        raise typer.Exit(1)

    with trace_scope(trace, "flow switch", domain="flow", target=target):
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
    pr: Annotated[
        int | None, typer.Option("--pr", help="PR number to resolve head branch from")
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Close flow and delete branch."""
    with trace_scope(trace, "flow done", domain="flow"):
        service = FlowService()
        target_branch = (
            resolve_target_branch(branch, pr) or service.get_current_branch()
        )

        logger.bind(command="flow done", branch=target_branch).info("Closing flow")

        flow_status = service.get_flow_status(target_branch)
        if not flow_status:
            typer.echo(
                f"Error: 当前分支 '{target_branch}' 没有 flow\n"
                "先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支",
                err=True,
            )
            raise typer.Exit(1)

        service.close_flow(target_branch, check_pr=True)

        typer.echo(f"Flow closed, branch '{target_branch}' deleted")


def blocked(
    branch: Annotated[str | None, typer.Option("--branch", help="Branch name")] = None,
    pr: Annotated[
        int | None, typer.Option("--pr", help="PR number to resolve head branch from")
    ] = None,
    reason: Annotated[
        str | None, typer.Option("--reason", help="Blocking reason")
    ] = None,
    task: Annotated[
        int | None, typer.Option("--task", help="Dependency issue number")
    ] = None,
    by: Annotated[
        int | None, typer.Option("--by", help="Dependency issue number")
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Mark flow as blocked.

    If --task/--by is provided, automatically adds dependency issue link.

    Examples:
        vibe3 flow blocked --reason "等待外部反馈"
        vibe3 flow blocked --task 218
        vibe3 flow blocked --task 218 --reason "需要 #218 先完成"
    """
    with trace_scope(trace, "flow blocked", domain="flow"):
        service = FlowService()
        target_branch = (
            resolve_target_branch(branch, pr) or service.get_current_branch()
        )

        logger.bind(
            command="flow blocked",
            branch=target_branch,
            reason=reason,
            task=task,
            by=by,
        ).info("Blocking flow")

        flow_status = service.get_flow_status(target_branch)
        if not flow_status:
            typer.echo(
                f"Error: 当前分支 '{target_branch}' 没有 flow\n"
                "先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支",
                err=True,
            )
            raise typer.Exit(1)

        blocked_by_issue = task if task is not None else by
        service.block_flow(
            target_branch, reason=reason, blocked_by_issue=blocked_by_issue
        )

        msg = f"Flow blocked on branch '{target_branch}'"
        if reason:
            msg += f": {reason}"
        if blocked_by_issue:
            msg += f" (blocked by #{blocked_by_issue})"
        typer.echo(msg)


def aborted(
    branch: Annotated[str | None, typer.Option("--branch", help="Branch name")] = None,
    pr: Annotated[
        int | None, typer.Option("--pr", help="PR number to resolve head branch from")
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Abort flow and delete branch."""
    with trace_scope(trace, "flow aborted", domain="flow"):
        service = FlowService()
        target_branch = (
            resolve_target_branch(branch, pr) or service.get_current_branch()
        )

        logger.bind(command="flow aborted", branch=target_branch).info("Aborting flow")

        flow_status = service.get_flow_status(target_branch)
        if not flow_status:
            typer.echo(
                f"Error: 当前分支 '{target_branch}' 没有 flow\n"
                "先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支",
                err=True,
            )
            raise typer.Exit(1)

        service.abort_flow(target_branch)

        typer.echo(f"Flow aborted, branch '{target_branch}' deleted")
