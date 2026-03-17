#!/usr/bin/env python3
"""Flow command handlers."""

import json
from typing import Annotated, Literal, Optional

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.services.flow_service import FlowService
from vibe3.ui.flow_ui import (
    render_flow_bound,
    render_flow_created,
    render_flow_status,
    render_flow_status_table,
    render_flows_table,
)

app = typer.Typer(help="Manage logic flows (branch-centric)")


@app.command()
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[Optional[str], typer.Option(help="Task ID to bind")] = None,
    actor: Annotated[str, typer.Option(help="Actor creating the flow")] = "claude",
) -> None:
    """Create a new flow."""
    logger.bind(command="flow new", name=name, task=task, actor=actor).info(
        "Creating new flow"
    )

    git = GitClient()
    service = FlowService()
    branch = git.get_current_branch()
    flow = service.create_flow(slug=name, branch=branch, task_id=task, actor=actor)
    render_flow_created(flow, task)


@app.command()
def bind(
    task_id: Annotated[str, typer.Argument(help="Task ID to bind")],
    actor: Annotated[str, typer.Option(help="Actor binding the task")] = "claude",
) -> None:
    """Bind a task to current flow."""
    logger.bind(command="flow bind", task_id=task_id, actor=actor).info(
        "Binding task to flow"
    )

    git = GitClient()
    service = FlowService()
    branch = git.get_current_branch()
    flow = service.bind_flow(branch=branch, task_id=task_id, actor=actor)
    render_flow_bound(flow, task_id)


@app.command()
def show(
    flow_name: Annotated[Optional[str], typer.Argument(help="Flow to show")] = None,
) -> None:
    """Show flow details."""
    logger.bind(command="flow show", flow_name=flow_name).info("Showing flow details")

    git = GitClient()
    service = FlowService()
    branch = flow_name if flow_name else git.get_current_branch()
    status = service.get_flow_status(branch)
    if not status:
        logger.error(f"Flow not found: {branch}")
        raise typer.Exit(1)
    render_flow_status(status)


@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Show flow status."""
    logger.bind(command="flow status", json_output=json_output).info(
        "Getting flow status"
    )

    git = GitClient()
    service = FlowService()
    branch = git.get_current_branch()
    flow_status = service.get_flow_status(branch)
    if json_output:
        output = flow_status.model_dump() if flow_status else {}
        typer.echo(json.dumps(output, indent=2, default=str))
    else:
        if not flow_status:
            logger.info("No active flow on current branch")
            raise typer.Exit(0)
        render_flow_status_table(flow_status)


@app.command()
def list(
    status_filter: Annotated[
        Optional[Literal["active", "idle", "missing", "stale"]],
        typer.Option("--status", help="Filter by status"),
    ] = None,
) -> None:
    """List all flows."""
    logger.bind(command="flow list", status_filter=status_filter).info("Listing flows")

    service = FlowService()
    flows = service.list_flows(status=status_filter)
    if not flows:
        logger.info("No flows found")
        raise typer.Exit(0)
    render_flows_table(flows)
