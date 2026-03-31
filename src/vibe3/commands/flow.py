#!/usr/bin/env python3
"""Flow command handlers."""

import json
from typing import Annotated, List, Literal

import typer
from loguru import logger

from vibe3.commands.common import trace_scope
from vibe3.commands.flow_lifecycle import blocked
from vibe3.commands.flow_status import show, status
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService
from vibe3.ui.console import console
from vibe3.ui.flow_ui import render_flow_created, render_flows_table

FlowNameArg = Annotated[
    str | None,
    typer.Argument(help="Flow name (defaults to current branch name)"),
]
IssueArg = Annotated[
    str, typer.Argument(help="Issue reference to bind as task/related/dependency")
]
TaskOption = Annotated[str | None, typer.Option(help="Issue reference to bind as task")]
TaskTailArg = Annotated[
    List[str] | None,
    typer.Argument(hidden=True),
]
AddTaskOption = Annotated[
    str | None,
    typer.Option(help="Task issue reference (e.g., 123, #123, or issue URL)"),
]
SpecOption = Annotated[
    str | None, typer.Option("--spec", help="Spec file path or issue reference")
]
TraceOption = Annotated[
    bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
]
JsonOption = Annotated[bool, typer.Option("--json", help="JSON 格式输出")]
ActorOption = Annotated[
    str | None,
    typer.Option(
        "--actor",
        "-a",
        help="Flow 默认署名（示例: codex/gpt-5.4）",
    ),
]
StatusFilterOption = Annotated[
    Literal["active", "blocked", "done", "stale"] | None,
    typer.Option("--status", help="Filter by status"),
]
BindRoleOption = Annotated[
    Literal["task", "related", "dependency"],
    typer.Option("--role", help="Issue role (task, related, or dependency)"),
]

app = typer.Typer(
    help="Manage logic flows.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _merge_issue_refs(
    primary: str | None,
    tail: list[str] | None,
    *,
    primary_hint: str,
) -> str | list[str] | None:
    """Validate and merge issue refs from command arguments."""
    tail = tail or []
    if not tail:
        return primary
    if primary is None:
        raise ValueError(f"Additional issue refs require '{primary_hint}' prefix.")
    return [primary, *tail]


@app.command(name="add")
def add(
    name: FlowNameArg = None,
    task: AddTaskOption = None,
    task_tail: TaskTailArg = None,
    spec: SpecOption = None,
    actor: ActorOption = None,
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """Add flow to current branch (idempotent)."""
    flow_service = FlowService()
    task_service = TaskService()
    with trace_scope(trace, "flow add", name=name):
        try:
            name = flow_service.resolve_flow_name(name)
            task_refs = _merge_issue_refs(
                task, task_tail, primary_hint="--task <issue>"
            )
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error

        # Register flow via FlowService instead of FlowUsecase
        flow = flow_service.ensure_flow_for_branch(
            branch=flow_service.get_current_branch(), slug=name
        )

        # Link issues
        from vibe3.utils.issue_ref import parse_issue_number

        if task_refs:
            refs: List[str] = (
                [task_refs] if isinstance(task_refs, str) else list(task_refs)
            )
            for ref in refs:
                issue_number = parse_issue_number(ref)
                task_service.link_issue(flow.branch, issue_number, "task", actor=actor)

        if spec:
            flow_service.bind_spec(flow.branch, spec, actor)

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(
                flow,
                (
                    " ".join(task_refs)
                    if task_refs is not None and not isinstance(task_refs, str)
                    else task_refs
                ),
            )


@app.command()
def bind(
    issue: IssueArg,
    issue_tail: TaskTailArg = None,
    role: BindRoleOption = "task",
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """Bind an issue to current flow."""
    from vibe3.utils.issue_ref import parse_issue_number

    issue_refs = _merge_issue_refs(issue, issue_tail, primary_hint="<issue>")
    if issue_refs is None:  # pragma: no cover - defensive
        raise typer.BadParameter("Missing issue reference")
    refs: List[str] = [issue_refs] if isinstance(issue_refs, str) else issue_refs
    with trace_scope(trace, "flow bind", issue=issue_refs, role=role):
        logger.bind(command="flow bind", issue=issue_refs, role=role).info(
            "Binding issue to flow"
        )
        try:
            flow_service = FlowService()
            task_service = TaskService()
            branch = flow_service.get_current_branch()

            links = []
            for ref in refs:
                issue_number = parse_issue_number(ref)
                link = task_service.link_issue(branch, issue_number, role, actor=None)
                links.append(link)

            if json_output:
                if len(links) == 1:
                    typer.echo(json.dumps(links[0].model_dump(), indent=2, default=str))
                else:
                    typer.echo(
                        json.dumps(
                            [link.model_dump() for link in links], indent=2, default=str
                        )
                    )
            else:
                for link in links:
                    message = (
                        f"[green]✓[/] Issue #{link.issue_number} linked as {role} "
                        f"to flow {link.branch}"
                    )
                    console.print(message)
        except ValueError:
            logger.error(f"Invalid issue format: {issue_refs}")
            raise typer.BadParameter(f"Invalid issue format: {issue_refs}")


@app.command(name="list")
def list_flows(
    status_filter: StatusFilterOption = None,
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """List all flows."""
    with trace_scope(trace, "flow list"):
        logger.bind(command="flow list", status_filter=status_filter).info(
            "Listing flows"
        )

        service = FlowService()
        flows = service.list_flows(status=status_filter)

        if not flows:
            logger.info("No flows found")
            raise typer.Exit(0)

        if json_output:
            typer.echo(
                json.dumps([f.model_dump() for f in flows], indent=2, default=str)
            )
        else:
            render_flows_table(flows)


# Register lifecycle commands from flow_lifecycle.py
app.command(name="blocked")(blocked)
app.command(name="show")(show)
app.command(name="status")(status)
