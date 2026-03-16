#!/usr/bin/env python3
"""Task command handlers."""
import re
from typing import Literal

import typer
from rich import print

from vibe3.clients.git_client import GitClient
from vibe3.services.task_service import TaskService
from vibe3.ui.task_ui import render_issue_linked

app = typer.Typer(help="Manage execution tasks")


def parse_issue_url(issue_url: str) -> int:
    """Parse issue number from GitHub URL.

    Args:
        issue_url: GitHub issue URL or issue number

    Returns:
        Issue number

    Examples:
        "https://github.com/org/repo/issues/123" -> 123
        "123" -> 123
    """
    # If it's just a number, return it
    if issue_url.isdigit():
        return int(issue_url)

    # Try to extract from GitHub URL
    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", issue_url)
    if match:
        return int(match.group(1))

    raise ValueError(f"Invalid issue URL or number: {issue_url}")


@app.command()
def list() -> None:
    """List all tasks."""
    print("[cyan]Tasks:[/] No tasks found")


@app.command()
def show(
    task_id: str = typer.Argument(..., help="Task ID")
) -> None:
    """Show task details."""
    print(f"[cyan]Task:[/] {task_id}")


@app.command()
def link(
    issue_url: str = typer.Argument(..., help="Issue URL or number"),
    role: Literal["task", "related"] = typer.Option(
        "related", help="Issue role (task/related)"
    ),
    actor: str = typer.Option("unknown", help="Actor linking the issue")
) -> None:
    """Link an issue to current flow.

    Args:
        issue_url: GitHub issue URL or issue number
        role: Issue role (task for primary, related for secondary)
        actor: Actor performing the link operation
    """
    try:
        # Parse issue number
        issue_number = parse_issue_url(issue_url)

        # Get current branch
        git = GitClient()
        branch = git.get_current_branch()

        # Link issue via service
        service = TaskService()
        link = service.link_issue(branch, issue_number, role, actor)

        # Render success
        render_issue_linked(link)

    except ValueError as e:
        print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    except Exception as e:
        print(f"[red]Unexpected error:[/] {e}")
        raise typer.Exit(1)
