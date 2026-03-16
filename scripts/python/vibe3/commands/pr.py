#!/usr/bin/env python3
"""PR command handlers."""
from typing import Optional

import typer

from vibe3.services.pr_service import PRService
from vibe3.models.pr import PRMetadata
from vibe3.ui.pr_ui import (
    render_pr_created,
    render_pr_details,
    render_pr_ready,
    render_pr_merged,
    render_version_bump,
    render_error,
)

app = typer.Typer(help="Manage Pull Requests")


@app.command()
def draft(
    title: str = typer.Option(..., "--title", "-t", help="PR title"),
    body: str = typer.Option("", "--body", "-b", help="PR description"),
    base: str = typer.Option("main", "--base", help="Base branch name"),
    task_issue: Optional[int] = typer.Option(None, "--task", help="Task issue number"),
    flow_slug: Optional[str] = typer.Option(None, "--flow", help="Flow slug"),
    spec_ref: Optional[str] = typer.Option(None, "--spec", help="Spec reference path"),
    planner: Optional[str] = typer.Option(None, "--planner", help="Planner agent"),
    executor: Optional[str] = typer.Option(None, "--executor", help="Executor agent"),
) -> None:
    """Create draft PR."""
    try:
        service = PRService()

        # Build metadata if any provided
        metadata = None
        if any([task_issue, flow_slug, spec_ref, planner, executor]):
            metadata = PRMetadata(
                task_issue=task_issue,
                flow_slug=flow_slug,
                spec_ref=spec_ref,
                planner=planner,
                executor=executor,
            )

        pr = service.create_draft_pr(
            title=title,
            body=body,
            base_branch=base,
            metadata=metadata,
        )

        render_pr_created(pr)

    except Exception as e:
        render_error(f"Failed to create draft PR: {e}")
        raise typer.Exit(1)


@app.command()
def show(
    pr_number: Optional[int] = typer.Argument(None, help="PR number"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch name"),
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
        render_error(f"Failed to get PR: {e}")
        raise typer.Exit(1)


@app.command()
def ready(
    pr_number: int = typer.Argument(..., help="PR number")
) -> None:
    """Mark PR as ready for review."""
    try:
        service = PRService()
        pr = service.mark_ready(pr_number)
        render_pr_ready(pr)

    except Exception as e:
        render_error(f"Failed to mark PR as ready: {e}")
        raise typer.Exit(1)


@app.command()
def merge(
    pr_number: int = typer.Argument(..., help="PR number")
) -> None:
    """Merge PR."""
    try:
        service = PRService()
        pr = service.merge_pr(pr_number)
        render_pr_merged(pr)

    except Exception as e:
        render_error(f"Failed to merge PR: {e}")
        raise typer.Exit(1)


@app.command()
def version_bump(
    pr_number: int = typer.Argument(..., help="PR number"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Task group (feature/bug/docs/chore)"),
) -> None:
    """Calculate version bump for PR."""
    try:
        service = PRService()
        response = service.calculate_version_bump(pr_number, group)
        render_version_bump(response)

    except Exception as e:
        render_error(f"Failed to calculate version bump: {e}")
        raise typer.Exit(1)