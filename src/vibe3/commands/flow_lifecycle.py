"""Flow lifecycle commands - blocked."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.common import enable_method_trace
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.exceptions import SystemError, UserError
from vibe3.services.branch_arg import resolve_branch_arg
from vibe3.services.convention_resolver import ConventionResolver
from vibe3.services.flow_rebuild_usecase import FlowRebuildUsecase
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_context_loader import load_issue_info
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.pr_branch_resolver import resolve_command_branch
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


def rebuild(
    issue_number: Annotated[
        int | None, typer.Argument(help="Issue number to rebuild")
    ] = None,
    branch_opt: Annotated[
        str | None, typer.Option("--branch", help="Branch name or issue number")
    ] = None,
    pr_opt: Annotated[
        int | None, typer.Option("--pr", help="PR number to resolve branch from")
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
        vibe3 flow rebuild 123 --yes                     # Rebuild issue #123
        vibe3 flow rebuild --branch task/issue-123 --yes # Rebuild via branch
        vibe3 flow rebuild --pr 456 --yes                # Rebuild via PR number
    """
    # Validate that exactly one target is provided
    provided = [
        name
        for opt, name in [
            (branch_opt, "--branch"),
            (pr_opt, "--pr"),
            (issue_number, "<issue-number>"),
        ]
        if opt is not None
    ]

    if len(provided) == 0:
        typer.echo(
            "Error: Must specify issue number, --branch, or --pr",
            err=True,
        )
        raise typer.Exit(1)

    if len(provided) > 1:
        typer.echo(
            f"错误：不能同时使用 {', '.join(provided)}，请只指定一个目标。",
            err=True,
        )
        raise typer.Exit(1)

    service = FlowService()

    # Resolve target branch
    if branch_opt is not None or pr_opt is not None:
        position_arg = str(issue_number) if issue_number is not None else None
        try:
            target_branch = resolve_command_branch(
                branch_opt=branch_opt,
                pr_opt=pr_opt,
                position_arg=position_arg,
                flow_service=service,
                allow_no_flow=True,  # rebuild can work even without existing flow
            )
        except (UserError, SystemError) as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

        # Parse issue number from target_branch for output message
        issue_svc = IssueFlowService(store=service.store)
        resolved_issue = issue_svc.parse_issue_number_any(target_branch)
        if resolved_issue is None:
            typer.echo(
                f"Error: 无法从分支 '{target_branch}' 解析 issue 编号",
                err=True,
            )
            raise typer.Exit(1)
        resolved_issue_number = resolved_issue
    else:
        # Use positional issue_number
        assert issue_number is not None
        resolved_issue_number = issue_number
        target_branch = (
            ConventionResolver.from_repo()
            .resolve()
            .branch.canonical_branch(issue_number)
        )

    if not yes:
        typer.echo(
            "[dry-run mode] Would hard rebuild "
            f"issue #{resolved_issue_number} at branch {target_branch}. "
            "Use --yes to execute."
        )
        return

    from vibe3.clients.github_client import GitHubClient

    config = load_orchestra_config()
    issue = load_issue_info(resolved_issue_number, config=config, github=GitHubClient())
    result = FlowRebuildUsecase().rebuild_issue_flow(
        issue=issue,
        branch=target_branch,
        reason="manual flow rebuild",
        include_remote=not keep_remote,
        ensure_worktree=not no_worktree,
    )
    typer.echo(f"Rebuilt flow for issue #{resolved_issue_number}: {result}")


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register flow lifecycle commands."""
    app.command(name="blocked")(blocked)
    app.command(name="rebuild")(rebuild)
