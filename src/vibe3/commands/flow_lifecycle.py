"""Flow lifecycle commands - blocked."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.common import enable_method_trace
from vibe3.config import load_orchestra_config
from vibe3.services import (
    FlowRebuildUsecase,
    FlowService,
    load_issue_info,
    resolve_branch_and_issue,
    resolve_branch_arg,
)


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
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Mark flow as blocked.

    If --task is provided, automatically adds dependency issue link.

    If no flow exists for the branch and the branch name follows task/dev convention,
    automatically calls flow update to create branch + flow (no worktree).

    Examples:
        vibe3 flow blocked --reason "等待外部反馈"
        vibe3 flow blocked --task 218
        vibe3 flow blocked --branch task/issue-1212 --task 467
    """
    if trace:
        enable_method_trace()

    if reason is not None and task is not None:
        typer.echo("Error: 不能同时指定 --reason 与 --task", err=True)
        raise typer.Exit(1)

    service = FlowService()

    target_branch = resolve_branch_arg(branch)

    logger.bind(
        command="flow blocked",
        branch=target_branch,
        reason=reason,
        task=task,
    ).info("Blocking flow")

    # Check if flow exists
    flow_status = service.get_flow_status(target_branch)

    if not flow_status:
        # Lazy: only resolve issue_number when flow doesn't exist
        _, issue_number = resolve_branch_and_issue(branch)
        if issue_number:
            logger.bind(
                branch=target_branch,
                issue_number=issue_number,
            ).info("Auto-creating flow via flow update (no worktree)")

            # Call flow update to create branch + flow
            from vibe3.commands.flow_manage import update

            try:
                update(
                    branch_arg=str(issue_number),  # Positional issue number
                    name=f"issue-{issue_number}",
                    actor=None,
                    spec=None,
                    trace=trace,
                    output_format="table",
                    json_output=False,
                )
            except typer.Exit:
                # Let typer.Exit propagate (normal CLI exit)
                raise
            except Exception as exc:
                logger.bind(
                    branch=target_branch,
                    issue_number=issue_number,
                    error=str(exc),
                ).error("Failed to auto-create flow")
                typer.echo(
                    f"Error: 无法自动创建 flow: {exc}\n"
                    f"请手动执行 `vibe3 flow update {issue_number}`",
                    err=True,
                )
                raise typer.Exit(1) from exc
        else:
            # No flow and not an issue branch - require manual creation
            typer.echo(
                f"Error: 目标分支 '{target_branch}' 没有 flow\n"
                "先执行 `vibe3 flow update <branch>` 或切到已有 flow 的分支",
                err=True,
            )
            raise typer.Exit(1)

    # Now block the flow
    service.block_flow(target_branch, reason=reason, blocked_by_issue=task)

    msg = f"Flow blocked on branch '{target_branch}'"
    if reason:
        msg += f": {reason}"
    if task:
        msg += f" (blocked by #{task})"
    typer.echo(msg)


def rebuild(
    issue_number: Annotated[
        int | None, typer.Argument(help="Issue number to rebuild")
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name or issue number"),
    ] = None,
    keep_remote: Annotated[
        bool,
        typer.Option("--keep-remote", help="Keep remote branch during rebuild"),
    ] = False,
    no_worktree: Annotated[
        bool,
        typer.Option("--no-worktree", help="Recreate flow without creating worktree"),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Execute rebuild (default dry-run)"),
    ] = False,
) -> None:
    """Hard rebuild an issue flow scene.

    This deletes the old task flow/worktree/branch scene, recreates the flow,
    appends a rebuild handoff event, and clears blocked state through the
    label-auto resume path.

    Examples:
        vibe3 flow rebuild 123
        vibe3 flow rebuild --branch task/issue-123
        vibe3 flow rebuild --branch 123
    """
    if branch is not None and issue_number is not None:
        typer.echo("Error: 不能同时指定 --branch 和位置参数", err=True)
        raise typer.Exit(1)
    if branch is None and issue_number is None:
        typer.echo("Error: 需要指定 issue number 或 --branch", err=True)
        raise typer.Exit(1)

    # Unified resolution: both "123" and "task/issue-123" work via
    # resolve_branch_and_issue
    input_arg = branch if branch is not None else str(issue_number)
    target_branch, resolved_issue_number = resolve_branch_and_issue(input_arg)

    # Use provided issue_number or derive from resolved branch
    if issue_number is None:
        issue_number = resolved_issue_number
        if issue_number is None:
            typer.echo(f"Error: 无法从 '{branch}' 解析 issue number", err=True)
            raise typer.Exit(1)
    if not yes:
        typer.echo(
            "[dry-run mode] Would hard rebuild "
            f"issue #{issue_number} at branch {target_branch}. Use --yes to execute."
        )
        return

    from vibe3.clients import GitHubClient

    config = load_orchestra_config()
    issue = load_issue_info(issue_number, config=config, github=GitHubClient())
    result = FlowRebuildUsecase().rebuild_issue_flow(
        issue=issue,
        branch=target_branch,
        reason="manual flow rebuild",
        include_remote=not keep_remote,
        ensure_worktree=not no_worktree,
    )
    typer.echo(f"Rebuilt flow for issue #{issue_number}: {result}")


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register flow lifecycle commands."""
    app.command(name="blocked")(blocked)
    app.command(name="rebuild")(rebuild)
