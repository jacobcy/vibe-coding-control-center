#!/usr/bin/env python3
"""PR command handlers."""

from typing import Optional

import typer

from vibe3.services.pr_service import PRService
from vibe3.models.pr import PRMetadata
from vibe3.ui.pr_ui import (
    render_error, render_pr_created, render_pr_details, render_pr_merged, render_pr_ready,
    render_pr_review, render_version_bump,
)

app = typer.Typer(help="Manage Pull Requests")


def _handle_error(message: str, error: Exception) -> None:
    """Handle error and exit."""
    render_error(f"{message}: {error}")
    raise typer.Exit(1)


@app.command()
def draft(
    title: str = typer.Option(..., "-t", help="PR title"),
    body: str = typer.Option("", "-b", help="PR description"),
    base: str = typer.Option("main", help="Base branch"),
    task: Optional[int] = typer.Option(None, help="Task issue #"),
    flow: Optional[str] = typer.Option(None, help="Flow slug"),
    spec: Optional[str] = typer.Option(None, help="Spec reference"),
    planner: Optional[str] = typer.Option(None, help="Planner agent"),
    executor: Optional[str] = typer.Option(None, help="Executor agent"),
) -> None:
    """Create draft PR."""
    try:
        service = PRService()
        metadata = None
        if any([task, flow, spec, planner, executor]):
            metadata = PRMetadata(task_issue=task, flow_slug=flow, spec_ref=spec,
                                   planner=planner, executor=executor)
        pr = service.create_draft_pr(title=title, body=body, base_branch=base, metadata=metadata)
        render_pr_created(pr)
    except Exception as e:
        _handle_error("Failed to create draft PR", e)


@app.command()
def show(
    pr_number: Optional[int] = typer.Argument(None, help="PR number"),
    branch: Optional[str] = typer.Option(None, "-b", help="Branch name"),
) -> None:
    """Show PR details."""
    try:
        service = PRService()
        pr = service.get_pr(pr_number, branch)
        if not pr:
            render_error("PR not found")
            raise typer.Exit(1)
        render_pr_details(pr)
    except Exception as e:
        _handle_error("Failed to get PR", e)


@app.command()
def ready(pr_number: int = typer.Argument(..., help="PR number")) -> None:
    """Mark PR as ready for review."""
    try:
        service = PRService()
        pr = service.mark_ready(pr_number)
        render_pr_ready(pr)
    except Exception as e:
        _handle_error("Failed to mark PR as ready", e)


@app.command()
def merge(pr_number: int = typer.Argument(..., help="PR number")) -> None:
    """Merge PR."""
    try:
        service = PRService()
        pr = service.merge_pr(pr_number)
        render_pr_merged(pr)
    except Exception as e:
        _handle_error("Failed to merge PR", e)


@app.command()
def version_bump(
    pr_number: int = typer.Argument(..., help="PR number"),
    group: Optional[str] = typer.Option(None, "-g", help="Task group"),
) -> None:
    """Calculate version bump for PR."""
    try:
        service = PRService()
        response = service.calculate_version_bump(pr_number, group)
        render_version_bump(response)
    except Exception as e:
        _handle_error("Failed to calculate version bump", e)


@app.command()
def review(
    pr_number: int = typer.Argument(..., help="PR number"),
    publish: bool = typer.Option(True, help="Publish review as comment"),
) -> None:
    """Review PR using local LLM (codex)."""
    try:
        service = PRService()
        response = service.review_pr(pr_number, publish)
        render_pr_review(response)
    except Exception as e:
        _handle_error("Failed to review PR", e)