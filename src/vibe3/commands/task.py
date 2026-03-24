#!/usr/bin/env python3
"""Task command handlers."""

import json
import re
from contextlib import contextmanager
from typing import Annotated, Iterator, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.task_bridge import bridge_app
from vibe3.exceptions import GitError
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


def parse_issue_ref(issue_ref: str) -> int:
    """Parse issue number from reference (number or GitHub URL)."""
    if issue_ref.isdigit():
        return int(issue_ref)
    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", issue_ref)
    if match:
        return int(match.group(1))
    raise ValueError(f"Invalid issue reference: {issue_ref}")


@app.command()
def list(
    issue: Annotated[
        str | None,
        typer.Option(
            "--issue",
            help="Issue number (or URL) — 查找该 issue 作为 related 角色关联的 flow",
        ),
    ] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List all tasks (flows with task issue bound)."""
    if trace:
        setup_logging(verbose=2)

    store = SQLiteClient()

    if issue is not None:
        issue_number = parse_issue_ref(issue)
        flows_data = store.get_flows_by_issue(issue_number, role="related")
        if not flows_data:
            typer.echo(f"No tasks linked to related issue #{issue_number}")
            return
        if json_output:
            typer.echo(json.dumps(flows_data, indent=2, default=str))
            return
        typer.echo(f"Tasks linked to related issue #{issue_number}:")
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
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show task details, including remote GitHub Project fields."""
    try:
        target_branch = branch or GitClient().get_current_branch()
    except GitError as e:
        typer.echo(
            f"Error: unable to resolve current branch ({e})",
            err=True,
        )
        raise typer.Exit(1)

    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="task show", domain="task", branch=target_branch)
        if trace
        else _noop()
    )
    with ctx:
        service = TaskService()
        view = service.hydrate(target_branch)

        if isinstance(view, HydrateError):
            if view.type == "binding_invalid":
                typer.echo(f"Error [{view.type}]: {view.message}", err=True)
                raise typer.Exit(1)

            task = service.get_task(target_branch)
            if not task:
                typer.echo(f"Task not found: {target_branch}", err=True)
                raise typer.Exit(1)
            if json_output:
                typer.echo(json.dumps(task.model_dump(), indent=2, default=str))
            else:
                typer.echo(f"Branch: {task.branch}")
                if task.task_issue_number:
                    typer.echo(f"Task Issue: #{task.task_issue_number}")
                typer.echo(f"Status (local flow): {task.flow_status}")
                typer.echo(
                    "[unbound] 运行 vibe3 task bridge 自动绑定，"
                    "或 vibe3 task bridge <issue_number> 指定"
                )
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

        store = SQLiteClient()
        related_issues = [
            lnk
            for lnk in store.get_issue_links(target_branch)
            if lnk["issue_role"] == "related"
        ]
        dependency_issues = [
            lnk
            for lnk in store.get_issue_links(target_branch)
            if lnk["issue_role"] == "dependency"
        ]
        if related_issues:
            typer.echo(
                "Related Issue(s): "
                + "  ".join(f"#{lnk['issue_number']}" for lnk in related_issues)
            )
        if dependency_issues:
            typer.echo(
                "Dependencies: "
                + "  ".join(f"#{lnk['issue_number']}" for lnk in dependency_issues)
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
    issue: Annotated[str, typer.Argument(help="Issue number (or URL)")],
    role: Annotated[
        Literal["related", "dependency"], typer.Option(help="Issue role")
    ] = "related",
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Link an issue to current flow."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="task link", domain="task") if trace else _noop()
    with ctx:
        try:
            issue_number = parse_issue_ref(issue)
            git = GitClient()
            branch = git.get_current_branch()
            service = TaskService()
            issue_link = service.link_issue(branch, issue_number, role)

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
        result = service.update_remote_task_status(branch, value)

        if isinstance(result, ProjectItemError):
            typer.echo(f"Error [{result.type}]: {result.message}", err=True)
            raise typer.Exit(1)

        typer.echo(f"✓ Remote task status updated to '{value}' on branch '{branch}'")
