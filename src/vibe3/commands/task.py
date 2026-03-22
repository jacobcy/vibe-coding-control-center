#!/usr/bin/env python3
"""Task command handlers."""

import json
import re
from contextlib import contextmanager
from typing import Annotated, Iterator, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.task_bridge import bridge_app
from vibe3.models.project_item import ProjectItemError
from vibe3.models.task_bridge import HydrateError
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.task_service import TaskService
from vibe3.ui.task_ui import render_issue_linked

app = typer.Typer(
    help="Manage execution tasks", no_args_is_help=True, rich_markup_mode="rich"
)
app.add_typer(bridge_app, name="bridge")


@contextmanager
def _noop() -> Iterator[None]:
    yield


def parse_issue_url(issue_url: str) -> int:
    """Parse issue number from GitHub URL or plain number."""
    if issue_url.isdigit():
        return int(issue_url)
    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", issue_url)
    if match:
        return int(match.group(1))
    raise ValueError(f"Invalid issue URL or number: {issue_url}")


@app.command()
def list(
    repo_issue: Annotated[
        int | None,
        typer.Option("--repo-issue", help="从 repo issue 反查所有关联 task"),
    ] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List all tasks (flows with task issue bound)."""
    if trace:
        setup_logging(verbose=2)

    from vibe3.clients.sqlite_client import SQLiteClient

    store = SQLiteClient()

    if repo_issue is not None:
        flows_data = store.get_flows_by_issue(repo_issue, role="repo")
        if not flows_data:
            typer.echo(f"No tasks linked to repo issue #{repo_issue}")
            return
        if json_output:
            typer.echo(json.dumps(flows_data, indent=2, default=str))
            return
        typer.echo(f"Tasks linked to repo issue #{repo_issue}:")
        for f in flows_data:
            task_num = f.get("task_issue_number")
            bound = "[bound]" if f.get("project_item_id") else "[unbound]"
            typer.echo(
                f"  #{task_num or '?'}  {f['flow_slug']}  "
                f"{f['flow_status']}  {bound}  branch={f['branch']}"
            )
        return

    all_flows = store.get_all_flows()
    tasks = [f for f in all_flows if f.get("task_issue_number")]
    if not tasks:
        typer.echo("No tasks found")
        return
    if json_output:
        typer.echo(json.dumps(tasks, indent=2, default=str))
        return
    for f in tasks:
        bound = "[bound]" if f.get("project_item_id") else "[unbound]"
        typer.echo(
            f"  #{f['task_issue_number']}  {f['flow_slug']}  "
            f"{f['flow_status']}  {bound}  branch={f['branch']}"
        )


@app.command()
def show(
    branch: Annotated[str, typer.Argument(help="Branch name")],
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show task details, including remote GitHub Project fields."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="task show", domain="task", branch=branch)
        if trace
        else _noop()
    )
    with ctx:
        service = TaskService()
        view = service.hydrate(branch)

        if isinstance(view, HydrateError):
            task = service.get_task(branch)
            if not task:
                typer.echo(f"Task not found: {branch}", err=True)
                raise typer.Exit(1)
            if json_output:
                typer.echo(json.dumps(task.model_dump(), indent=2, default=str))
            else:
                typer.echo(f"Branch: {task.branch}")
                if task.task_issue_number:
                    typer.echo(f"Task Issue: #{task.task_issue_number}")
                typer.echo(f"Status (local flow): {task.flow_status}")
                typer.echo("[unbound] 运行 vibe task bridge link-project <id> 绑定")
            return

        if json_output:
            typer.echo(json.dumps(view.model_dump(), indent=2, default=str))
            return

        bound_id = view.project_item_id.value if view.project_item_id else None
        bind_status = "[bound]" if bound_id else "[unbound]"
        typer.echo(f"Branch: {view.branch}")
        typer.echo(f"Project Item {bind_status}: {bound_id or 'N/A'}")

        if view.task_issue_number:
            typer.echo(f"Task Issue: #{view.task_issue_number.value}")

        from vibe3.clients.sqlite_client import SQLiteClient

        store = SQLiteClient()
        repo_issues = [
            lnk for lnk in store.get_issue_links(branch) if lnk["issue_role"] == "repo"
        ]
        if repo_issues:
            typer.echo(
                "Repo Issue(s): "
                + "  ".join(f"#{lnk['issue_number']}" for lnk in repo_issues)
            )

        if view.spec_ref:
            typer.echo(f"Spec Ref: {view.spec_ref.value}")
        if view.next_step:
            typer.echo(f"Next Step: {view.next_step.value}")
        if view.blocked_by:
            typer.echo(f"Blocked By: {view.blocked_by.value}")

        if view.offline_mode:
            typer.echo("[offline mode] 远端读取失败，仅显示本地 bridge 字段")
        else:
            if view.title:
                typer.echo(f"[remote] Title:    {view.title.value}")
            if view.status:
                typer.echo(f"[remote] Status:   {view.status.value}")
            if view.priority:
                typer.echo(f"[remote] Priority: {view.priority.value}")
            if view.assignees:
                typer.echo(f"[remote] Assignees: {', '.join(view.assignees.value)}")

        if view.identity_drift:
            typer.echo("[warning] identity_drift=True: 本地与远端 identity 不一致")


@app.command()
def link(
    issue_url: Annotated[str, typer.Argument(help="Issue URL or number")],
    role: Annotated[Literal["task", "repo"], typer.Option(help="Issue role")] = "repo",
    actor: Annotated[str, typer.Option(help="Actor linking the issue")] = "unknown",
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Link an issue to current flow."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="task link", domain="task") if trace else _noop()
    with ctx:
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


@app.command()
def status(
    value: Annotated[str, typer.Argument(help="目标状态值，如 'In Progress'、'Done'")],
    actor: Annotated[str, typer.Option(help="执行此操作的 actor")] = "unknown",
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Update remote GitHub Project task status (唯一合法写入路径)."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="task status", domain="task") if trace else _noop()
    with ctx:
        git = GitClient()
        branch = git.get_current_branch()
        service = TaskService()
        result = service.update_remote_task_status(branch, value, actor)

        if isinstance(result, ProjectItemError):
            typer.echo(f"Error [{result.type}]: {result.message}", err=True)
            raise typer.Exit(1)

        typer.echo(f"✓ Remote task status updated to '{value}' on branch '{branch}'")
