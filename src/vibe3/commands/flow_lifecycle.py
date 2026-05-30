"""Flow lifecycle commands - blocked."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.common import enable_method_trace
from vibe3.services import ConventionResolver, FlowService, resolve_branch_arg
from vibe3.utils.issue_ref import try_parse_issue_number


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

    # Early handling for issue number: resolve to canonical branch
    # before resolve_branch_arg. This avoids UserError from
    # resolve_issue_branch_input when flow doesn't exist
    issue_number_input = try_parse_issue_number(branch) if branch else None
    if issue_number_input is not None:
        convention = ConventionResolver.from_repo().resolve().branch
        target_branch = convention.canonical_branch(issue_number_input)
    else:
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
        # Try to auto-create flow if branch matches task/dev convention
        convention = ConventionResolver.from_repo().resolve().branch
        issue_number = convention.parse_issue_number(target_branch)

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


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register flow lifecycle commands."""
    app.command(name="blocked")(blocked)
