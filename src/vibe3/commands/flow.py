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
from vibe3.ui.flow_ui import render_flow_created

BranchArg = Annotated[
    str | None,
    typer.Argument(help="Branch to update (defaults to current)"),
]
IssueArg = Annotated[
    str,
    typer.Argument(
        metavar="<task-id>",
        help="Issue reference or <task-id> to bind as task/related/dependency",
    ),
]
TaskTailArg = Annotated[
    List[str] | None,
    typer.Argument(hidden=True),
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
NameOption = Annotated[
    str | None,
    typer.Option(
        "--name",
        "-n",
        help="Flow 名称/Slug (默认从 branch 推断)",
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
BindBranchOption = Annotated[
    str | None,
    typer.Option("--branch", help="Branch name (defaults to current branch)"),
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


def _resolve_bind_branch(flow_service: FlowService, branch: str | None) -> str:
    """Resolve target branch for flow bind.

    For explicit --branch, require an existing non-protected flow branch.
    For implicit branch selection, preserve current behavior by using the
    current branch directly.
    """
    if branch is None:
        return flow_service.get_current_branch()

    if flow_service._is_main_branch(branch):
        typer.echo(
            f"Error: 受保护分支 '{branch}' 不能直接绑定 issue",
            err=True,
        )
        raise typer.Exit(1)

    if flow_service.get_flow_status(branch) is None:
        typer.echo(
            f"Error: 目标分支 '{branch}' 没有 flow\n"
            "先运行 `vibe3 flow update <branch>` 注册 flow，或切换到该分支后再执行绑定",
            err=True,
        )
        raise typer.Exit(1)

    return branch


@app.command(name="update")
def update(
    branch: BranchArg = None,
    name: NameOption = None,
    actor: ActorOption = None,
    spec: SpecOption = None,
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """Update flow metadata (idempotent add/update)."""
    flow_service = FlowService()
    with trace_scope(trace, "flow update", branch=branch):
        if not branch:
            branch = flow_service.get_current_branch()

        # Register/Ensure flow
        flow = flow_service.ensure_flow_for_branch(branch=branch, slug=name)

        # Update metadata if explicitly provided — keep name and actor separate
        # to avoid silently writing worktree identity when only --name is given.
        if name or actor:
            updates: dict[str, object] = {}
            if name:
                updates["flow_slug"] = name
            if actor:
                from vibe3.services.signature_service import SignatureService

                updates["latest_actor"] = SignatureService.resolve_actor(
                    explicit_actor=actor
                )
            if updates:
                flow_service.update_flow_metadata(branch, **updates)
            # Re-fetch flow state
            updated = flow_service.get_flow_status(branch)
            if updated:
                flow = updated

        if spec:
            flow_service.bind_spec(flow.branch, spec, actor)

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow)


@app.command()
def bind(
    issue: IssueArg,
    issue_tail: TaskTailArg = None,
    branch: BindBranchOption = None,
    role: BindRoleOption = "task",
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """Bind an issue to a flow branch. (Usage: vibe flow bind <task-id>)"""
    from vibe3.utils.issue_ref import parse_issue_number

    issue_refs = _merge_issue_refs(issue, issue_tail, primary_hint="<issue>")
    if issue_refs is None:  # pragma: no cover - defensive
        raise typer.BadParameter("Missing issue reference")
    refs: List[str] = [issue_refs] if isinstance(issue_refs, str) else issue_refs
    with trace_scope(trace, "flow bind", issue=issue_refs, role=role, branch=branch):
        logger.bind(
            command="flow bind", issue=issue_refs, role=role, branch=branch
        ).info("Binding issue to flow")
        try:
            flow_service = FlowService()
            task_service = TaskService()
            target_branch = _resolve_bind_branch(flow_service, branch)

            links = []
            for ref in refs:
                issue_number = parse_issue_number(ref)
                link = task_service.link_issue(
                    target_branch,
                    issue_number,
                    role,
                    actor=None,
                )
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


# Register lifecycle commands from flow_lifecycle.py
app.command(name="blocked")(blocked)
app.command(name="show")(show)
app.command(name="status")(status)
