"""Flow lifecycle commands (new, switch, done, aborted)."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.flow_helpers import _noop
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.ui.flow_ui import render_flow_created


def new(
    name: Annotated[
        str | None,
        typer.Argument(help="Flow name (default: branch name without prefix)"),
    ] = None,
    issue: Annotated[
        str | None,
        typer.Option("--issue", help="Issue number (or URL) to bind as task"),
    ] = None,
    branch: Annotated[
        str,
        typer.Option("--branch", help="Start ref for new branch"),
    ] = "origin/main",
    save_unstash: Annotated[
        bool,
        typer.Option("--save-unstash", help="Stash and restore current changes"),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Create a new flow with a new branch."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="flow new", domain="flow", name=name)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(
            command="flow new",
            name=name,
            issue=issue,
            branch=branch,
            save_unstash=save_unstash,
        ).info("Creating new flow with branch")

        slug = name if name else "new-feature"
        service = FlowService()

        try:
            flow = service.create_flow_with_branch(
                slug=slug,
                start_ref=branch,
                save_unstash=save_unstash,
            )

            if issue is not None:
                from vibe3.commands.task import parse_issue_ref
                from vibe3.services.task_service import TaskService

                issue_number = parse_issue_ref(issue)
                TaskService(store=service.store).link_issue(
                    flow.branch, issue_number, role="task"
                )
                flow.task_issue_number = issue_number

            if json_output:
                typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
            else:
                render_flow_created(flow, issue)

        except Exception as e:
            if isinstance(e, Exception) and e.__class__.__name__ == "UserError":
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)
            raise


def switch(
    target: Annotated[str, typer.Argument(help="Branch name or flow slug")],
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Switch to an existing flow."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="flow switch", domain="flow", target=target)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow switch", target=target).info("Switching flow")

        service = FlowService()

        try:
            flow = service.switch_flow(target=target)

            if json_output:
                typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
            else:
                typer.echo(
                    f"✓ Switched to flow '{flow.flow_slug}' on branch '{flow.branch}'"
                )

        except Exception as e:
            if isinstance(e, Exception) and e.__class__.__name__ == "UserError":
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)
            raise


def done(
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name (default: current branch)"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip PR check and force close"),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Close a flow and delete its branch."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="flow done", domain="flow") if trace else _noop()
    with ctx:
        logger.bind(command="flow done", branch=branch, yes=yes).info("Closing flow")

        git = GitClient()
        target_branch = branch if branch else git.get_current_branch()
        service = FlowService()

        try:
            service.close_flow(branch=target_branch, check_pr=not yes)
            typer.echo(f"✓ Flow closed and branch '{target_branch}' deleted")

        except Exception as e:
            if isinstance(e, Exception) and e.__class__.__name__ == "UserError":
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)
            raise


def aborted(
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name (default: current branch)"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Abort a flow and delete its branch."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="flow aborted", domain="flow") if trace else _noop()
    with ctx:
        logger.bind(command="flow aborted", branch=branch).info("Aborting flow")

        git = GitClient()
        target_branch = branch if branch else git.get_current_branch()
        service = FlowService()

        try:
            service.abort_flow(branch=target_branch)
            typer.echo(f"✓ Flow aborted and branch '{target_branch}' deleted")

        except Exception as e:
            if isinstance(e, Exception) and e.__class__.__name__ == "UserError":
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)
            raise
