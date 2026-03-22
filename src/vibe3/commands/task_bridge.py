"""Task bridge sub-commands — link current branch to GitHub Project item."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.models.project_item import LinkError, ProjectItemError
from vibe3.observability.logger import setup_logging
from vibe3.services.task_service import TaskService

bridge_app = typer.Typer(
    help="Task bridge commands for linking to GitHub Project",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@bridge_app.command("link-project")
def bridge_link_project(
    project_item_id: Annotated[
        str | None,
        typer.Argument(help="GitHub Project item ID"),
    ] = None,
    from_issue: Annotated[
        int | None,
        typer.Option("--from-issue", help="通过 issue number 反查并绑定 Project item"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="强制覆盖已有绑定"),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Link current branch to a GitHub Project item.

    Usage:
      vibe task bridge link-project <project_item_id>
      vibe task bridge link-project --from-issue <issue_number>
    """
    import json

    if trace:
        setup_logging(verbose=2)

    if not project_item_id and not from_issue:
        typer.echo(
            "Error: 请提供 project_item_id 或 --from-issue <issue_number>", err=True
        )
        raise typer.Exit(1)

    git = GitClient()
    branch = git.get_current_branch()
    service = TaskService()

    if from_issue is not None:
        client = service._get_project_client()
        if not client:
            typer.echo(
                "Error: GitHubProjectClient 未初始化，"
                "请检查 config/settings.yaml 中的 github_project 配置",
                err=True,
            )
            raise typer.Exit(1)

        found = client.find_item_by_issue(from_issue)
        if isinstance(found, ProjectItemError):
            typer.echo(f"Error [{found.type}]: {found.message}", err=True)
            raise typer.Exit(1)
        project_item_id = found.item_id

    assert project_item_id is not None

    result = service.link_project_item(branch, project_item_id, force=force)

    if isinstance(result, LinkError):
        typer.echo(f"Error [{result.type}]: {result.message}", err=True)
        raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps(result.model_dump(), indent=2, default=str))
    else:
        typer.echo(
            f"✓ Branch '{branch}' linked to GitHub Project item '{project_item_id}'"
        )
        if result.project_node_id:
            typer.echo(f"  node_id: {result.project_node_id}")

    logger.bind(domain="task", action="bridge_link_project", branch=branch).info(
        "Bridge link-project done"
    )
