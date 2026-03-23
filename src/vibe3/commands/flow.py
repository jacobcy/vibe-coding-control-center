#!/usr/bin/env python3
"""Flow command handlers."""

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Iterator, Literal

import typer
from loguru import logger
from rich.console import Console
from rich.prompt import Prompt

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.commands.flow_lifecycle import aborted as _aborted
from vibe3.commands.flow_lifecycle import blocked as _blocked
from vibe3.commands.flow_lifecycle import done as _done
from vibe3.commands.flow_lifecycle import switch as _switch
from vibe3.commands.flow_status import show as _show
from vibe3.commands.flow_status import status as _status
from vibe3.commands.task import parse_issue_ref
from vibe3.config.settings import VibeConfig
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.ai_service import AIService
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService
from vibe3.ui.flow_ui import render_flow_created, render_flows_table
from vibe3.ui.task_ui import render_issue_linked

app = typer.Typer(
    help="Manage logic flows (branch-centric)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _default_flow_name(branch: str) -> str:
    return branch.split("/", 1)[1] if "/" in branch else branch


def _is_interactive(json_output: bool) -> bool:
    return not json_output and sys.stdin.isatty() and sys.stdout.isatty()


@app.command()
def new(
    name: Annotated[
        str | None, typer.Argument(help="Flow name (default: branch name)")
    ] = None,
    issue: Annotated[
        str | None, typer.Option("--issue", help="Issue number (or URL) to bind")
    ] = None,
    create_branch: Annotated[
        bool,
        typer.Option("--create-branch", "-c", help="Create new branch (task/<name>)"),
    ] = False,
    start_ref: Annotated[
        str, typer.Option("--start-ref", help="Start ref for new branch")
    ] = "origin/main",
    ai: Annotated[
        bool, typer.Option("--ai", help="Use AI to suggest flow slug from issue")
    ] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Create a new flow. Use -c to create new branch, default uses current branch."""
    if trace:
        setup_logging(verbose=2)
    ctx = (
        trace_context(command="flow new", domain="flow", name=name)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow new", name=name, issue=issue).info("Creating flow")
        git = GitClient()
        console = Console()
        interactive = _is_interactive(json_output)
        slug = name

        if ai and issue is None:
            typer.echo("Error: --ai requires --issue", err=True)
            raise typer.Exit(1)

        if ai and issue is not None:
            issue_number = parse_issue_ref(issue)
            gh = GitHubClient()
            issue_data = gh.view_issue(issue_number)
            if issue_data is None:
                if interactive:
                    console.print(
                        f"[yellow]Warning: Could not fetch issue #{issue_number}[/]"
                    )
            elif isinstance(issue_data, dict):
                issue_title = issue_data.get("title", "")
                issue_body = issue_data.get("body")
                config = VibeConfig.get_defaults()
                prompts_path = Path("config/prompts.yaml")
                ai_service = AIService(config.ai, prompts_path=prompts_path)
                suggestions = ai_service.suggest_flow_slug(issue_title, issue_body)
                if suggestions:
                    if interactive:
                        console.print("\n[bold]AI Suggestions:[/]")
                        for i, suggestion in enumerate(suggestions, 1):
                            console.print(f"  {i}. {suggestion}")
                        choice = Prompt.ask("Choose (1-3) or enter name", default="1")
                        if choice.isdigit() and 1 <= int(choice) <= len(suggestions):
                            slug = suggestions[int(choice) - 1]
                        else:
                            slug = choice or None
                    else:
                        slug = suggestions[0]
                elif interactive:
                    console.print("[yellow]AI suggestion unavailable, using default[/]")

        if slug is None:
            current_branch = git.get_current_branch()
            slug = _default_flow_name(current_branch)

        if create_branch:
            branch_name = f"task/{slug}"
            if git.branch_exists(branch_name):
                console.print(f"[red]Error: Branch '{branch_name}' already exists.[/]")
                console.print(
                    f"[yellow]Hint: Use different name or 'vibe3 flow switch {slug}'[/]"
                )
                raise typer.Exit(1)
            service = FlowService()
            try:
                flow = service.create_flow_with_branch(slug=slug, start_ref=start_ref)
            except RuntimeError as e:
                console.print(f"[red]Error: {e}[/]")
                raise typer.Exit(1)
        else:
            branch = git.get_current_branch()
            service = FlowService()
            flow = service.create_flow(slug=slug, branch=branch)

        if issue is not None:
            issue_number = parse_issue_ref(issue)
            branch = git.get_current_branch()
            TaskService().link_issue(branch, issue_number, role="task")
            flow.task_issue_number = issue_number

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, str(flow.task_issue_number) if issue else None)


@app.command()
def bind(
    issue: Annotated[str, typer.Argument(help="Issue number (or URL)")],
    role: Annotated[
        Literal["task", "related", "dependency"],
        typer.Option(help="Issue role in flow"),
    ] = "task",
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Bind a task issue to current flow."""
    if trace:
        setup_logging(verbose=2)
    ctx = (
        trace_context(command="flow bind", domain="flow", issue=issue, role=role)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow bind", issue=issue, role=role).info(
            "Binding task to flow"
        )
        git = GitClient()
        branch = git.get_current_branch()
        try:
            issue_number = parse_issue_ref(issue)
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)
        task_service = TaskService()
        issue_link = task_service.link_issue(branch, issue_number, role=role)
        if json_output:
            typer.echo(json.dumps(issue_link.model_dump(), indent=2, default=str))
        else:
            render_issue_linked(issue_link)


@app.command()
def list(
    all_flows: Annotated[
        bool, typer.Option("--all", help="显示所有 flow（含历史）")
    ] = False,
    status_filter: Annotated[
        Literal["active", "blocked", "done", "stale"] | None, typer.Option("--status")
    ] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List flows. Default: active only. Use --all to include history."""
    if trace:
        setup_logging(verbose=2)
    ctx = trace_context(command="flow list", domain="flow") if trace else _noop()
    with ctx:
        logger.bind(
            command="flow list", all_flows=all_flows, status_filter=status_filter
        ).info("Listing flows")
        service = FlowService()
        flows = (
            service.list_flows(status=status_filter)
            if all_flows
            else service.list_flows(status=status_filter or "active")
        )
        if not flows:
            logger.info("No flows found")
            raise typer.Exit(0)
        if json_output:
            typer.echo(
                json.dumps([f.model_dump() for f in flows], indent=2, default=str)
            )
        else:
            render_flows_table(flows)


@app.command()
def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show flow details."""
    _show(branch=branch, trace=trace, json_output=json_output)


@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Show dashboard of all active flows."""
    _status(json_output=json_output, trace=trace)


@app.command()
def switch(
    target: Annotated[str, typer.Argument(help="Flow slug or branch name")],
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Switch to existing flow."""
    _switch(target, trace=trace, json_output=json_output)


@app.command()
def done(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Close flow and delete branch."""
    _done(branch=branch, yes=yes, trace=trace)


@app.command()
def blocked(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    reason: Annotated[str | None, typer.Option("--reason")] = None,
    by: Annotated[int | None, typer.Option("--by")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Mark flow as blocked. Use --by to link dependency issue."""
    _blocked(branch=branch, reason=reason, by=by, trace=trace)


@app.command()
def aborted(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Abort flow and delete branch."""
    _aborted(branch=branch, trace=trace)
