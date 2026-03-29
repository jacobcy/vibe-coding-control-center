#!/usr/bin/env python3
"""Flow command handlers."""

import json
from typing import Annotated, List, Literal

import typer
from loguru import logger

from vibe3.commands.common import trace_scope
from vibe3.commands.flow_lifecycle import aborted, blocked, done, switch
from vibe3.commands.flow_status import show, status
from vibe3.services.flow_service import FlowService
from vibe3.services.flow_usecase import FlowUsecase, FlowUsecaseError
from vibe3.services.handoff_service import HandoffService  # noqa: F401
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


def _print_flow_error(error: FlowUsecaseError) -> None:
    console.print(f"[red]Error: {error}[/]")
    if error.guidance:
        console.print(f"[yellow]{error.guidance}[/]")


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
            task_refs = FlowUsecase.validate_issue_refs(
                task, task_tail, primary_hint="--task <issue>"
            )
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error
        usecase = FlowUsecase.create(flow_service, task_service=task_service)
        logger.bind(command="flow add", name=name, task=task_refs).info("Adding flow")
        try:
            flow = usecase.add_flow(name=name, task=task_refs, spec=spec, actor=actor)
        except FlowUsecaseError as error:
            _print_flow_error(error)
            raise typer.Exit(1) from error
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error

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


@app.command(name="new", deprecated=True, hidden=True)
def new(
    name: FlowNameArg = None,
    task: TaskOption = None,
    spec: SpecOption = None,
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """Deprecated alias for `flow add`."""
    console.print(
        "[yellow]Warning: 'flow new' is deprecated. Use 'flow add' instead.[/]"
    )
    add(name, task, None, spec, None, trace, json_output)


@app.command(name="create")
def create(
    name: FlowNameArg = None,
    task: TaskOption = None,
    task_tail: TaskTailArg = None,
    spec: SpecOption = None,
    actor: ActorOption = None,
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            "-b",
            help="Base policy/branch: parent|current|main|<branch>.",
        ),
    ] = None,
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """Create a new branch with flow state."""
    flow_service = FlowService()
    task_service = TaskService()
    with trace_scope(trace, "flow create", name=name, base=base):
        try:
            name = flow_service.resolve_flow_name(name)
            task_refs = FlowUsecase.validate_issue_refs(
                task, task_tail, primary_hint="--task <issue>"
            )
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error
        usecase = FlowUsecase.create(flow_service, task_service=task_service)
        logger.bind(command="flow create", name=name, base=base, task=task_refs).info(
            "Creating flow with new branch"
        )
        try:
            flow = usecase.create_flow(
                name=name,
                base=base,
                task=task_refs,
                spec=spec,
                actor=actor,
            )
        except FlowUsecaseError as error:
            _print_flow_error(error)
            raise typer.Exit(1) from error
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error

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
    issue_refs = FlowUsecase.validate_issue_refs(
        issue, issue_tail, primary_hint="<issue>"
    )
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
            links = [
                FlowUsecase.create(flow_service, task_service=task_service).bind_issue(
                    ref, role
                )
                for ref in refs
            ]
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


@app.command()
def list(
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
app.command(name="switch")(switch)
app.command(name="done")(done)
app.command(name="blocked")(blocked)
app.command(name="aborted")(aborted)
app.command(name="show")(show)
app.command(name="status")(status)
