"""Task bridge commands — link current branch to GitHub Project item."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.models.project_item import LinkError
from vibe3.observability.logger import setup_logging
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService

bridge_app = typer.Typer(
    help="Task bridge commands for linking to GitHub Project",
    no_args_is_help=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
)


@bridge_app.callback()
def bridge(
    ctx: typer.Context,
    issue_number: Annotated[
        int | None,
        typer.Argument(
            help="Issue number to link (default: current flow's bound task)"
        ),
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
    """Link current branch's task issue to GitHub Project.

    Examples:
      vibe3 task bridge         # 自动使用当前 flow 绑定的 task issue
      vibe3 task bridge 100     # 指定 issue #100
      vibe3 task bridge 100 --force
    """
    if ctx.invoked_subcommand is not None:
        return

    if trace:
        setup_logging(verbose=2)

    cfg = VibeConfig.get_defaults()
    gh_cfg = cfg.github_project
    if not (gh_cfg.owner or gh_cfg.org) or not gh_cfg.project_number:
        _hint_missing_config()
        raise typer.Exit(1)

    flow_service = FlowService()
    branch = flow_service.get_current_branch()
    service = TaskService()

    if issue_number is None:
        flow_data = flow_service.store.get_flow_state(branch)
        issue_number = flow_data.get("task_issue_number") if flow_data else None
        if not issue_number:
            typer.echo(
                "Error: 当前 branch 尚未绑定 task issue，"
                "请先运行 vibe3 flow bind <issue_number> "
                "或直接指定: vibe3 task bridge <issue_number>",
                err=True,
            )
            raise typer.Exit(1)

    result = service.auto_link_issue_to_project(branch, issue_number)

    if isinstance(result, LinkError):
        if result.type == "already_bound" and not force:
            typer.echo(f"Error [{result.type}]: {result.message}", err=True)
            typer.echo("Hint: 使用 --force 强制覆盖", err=True)
            raise typer.Exit(1)
        elif result.type != "already_bound":
            typer.echo(f"Error [{result.type}]: {result.message}", err=True)
            raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps(result.model_dump(), indent=2, default=str))
    else:
        typer.echo(
            f"✓ Issue #{issue_number} linked to GitHub Project (branch: {branch})"
        )
        if hasattr(result, "project_item_id") and result.project_item_id:
            typer.echo(f"  project_item_id: {result.project_item_id}")

    logger.bind(domain="task", action="bridge_link_project", branch=branch).info(
        "Bridge link done"
    )


def _hint_missing_config() -> None:
    """提示用户在 settings.yaml 配置 github_project。"""
    typer.echo(
        "Error: GitHub Project 未配置。\n"
        "请在 config/settings.yaml 中设置：\n\n"
        "  github_project:\n"
        '    owner_type: "user"   # 或 "org"\n'
        '    owner: "<your-github-username-or-org>"\n'
        "    project_number: <project-number>",
        err=True,
    )
