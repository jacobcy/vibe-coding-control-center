"""PR creation commands."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.prompt import Prompt

from vibe3.commands.pr_helpers import build_base_resolution_usecase, noop_context
from vibe3.config.settings import VibeConfig
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.ai_service import AIService
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_created


def _is_interactive(json_output: bool, yaml_output: bool) -> bool:
    return (
        not json_output
        and not yaml_output
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    )


def register_create_command(app: typer.Typer) -> None:
    """Register pr create command."""

    @app.command()
    def create(
        title: Annotated[str, typer.Option("-t", help="PR title")] = "",
        body: Annotated[str, typer.Option("-b", help="PR description")] = "",
        base: Annotated[str | None, typer.Option(help="Base branch")] = None,
        ai: Annotated[
            bool,
            typer.Option("--ai", help="Use AI to suggest PR title and body"),
        ] = False,
        trace: Annotated[
            bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="JSON 格式输出")
        ] = False,
        yaml_output: Annotated[
            bool, typer.Option("--yaml", help="YAML 格式输出")
        ] = False,
    ) -> None:
        """Create draft PR.

        Metadata (task, flow, spec, planner, executor) is automatically
        read from the current flow state.
        """
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        ctx = (
            trace_context(command="pr create", domain="pr", title=title)
            if trace
            else noop_context()
        )
        with ctx:
            base_resolver = build_base_resolution_usecase()
            resolved_base = base_resolver.resolve_pr_create_base(base)
            logger.bind(command="pr create", title=title, base=resolved_base).info(
                "Creating PR"
            )

            pr_title = title
            pr_body = body
            interactive = _is_interactive(json_output, yaml_output)
            flow_service = FlowService()
            branch = flow_service.get_current_branch()
            flow_status = flow_service.get_flow_status(branch)
            if (
                not json_output
                and not yaml_output
                and (not flow_status or flow_status.task_issue_number is None)
            ):
                typer.echo(
                    "提示：当前 flow 还没有 task，建议先执行 "
                    "vibe3 flow bind <issue> --role task"
                )

            if ai and not title:
                console = Console()
                material = base_resolver.collect_branch_material(
                    base_branch=resolved_base,
                    branch=branch,
                )
                commits = material.commits
                changed_files = material.changed_files

                if not commits:
                    if interactive:
                        console.print(
                            (
                                "[yellow]No commits found, cannot generate "
                                "AI suggestions[/]"
                            )
                        )
                else:
                    config = VibeConfig.get_defaults()
                    prompts_path = Path("config/prompts.yaml")
                    ai_service = AIService(config.ai, prompts_path=prompts_path)
                    result = ai_service.suggest_pr_content(commits, changed_files)

                    if result:
                        suggested_title, suggested_body = result
                        if suggested_title:
                            if interactive:
                                console.print(
                                    f"\n[bold]Suggested title:[/] {suggested_title}"
                                )
                                use_suggested = Prompt.ask(
                                    "Use this title?",
                                    choices=["y", "n"],
                                    default="y",
                                )
                                if use_suggested == "y":
                                    pr_title = suggested_title
                                else:
                                    pr_title = Prompt.ask("Enter PR title")
                            else:
                                pr_title = suggested_title
                        if suggested_body:
                            if interactive:
                                console.print(
                                    f"\n[bold]Suggested body:[/]\n{suggested_body}"
                                )
                                use_body = Prompt.ask(
                                    "Use this body?",
                                    choices=["y", "n"],
                                    default="y",
                                )
                                if use_body == "y":
                                    pr_body = suggested_body or ""
                            else:
                                pr_body = suggested_body or ""
                    elif interactive:
                        console.print(
                            "[yellow]AI suggestion unavailable, using manual input[/]"
                        )

            if not pr_title:
                if interactive:
                    pr_title = Prompt.ask("Enter PR title")
                else:
                    typer.echo("Error: PR title is required", err=True)
                    raise typer.Exit(1)

            service = PRService()
            actor = "ai_assistant" if ai else "server"
            pr = service.create_draft_pr(
                title=pr_title,
                body=pr_body,
                base_branch=resolved_base,
                actor=actor,
            )

            if json_output:
                typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
            elif yaml_output:
                import yaml

                typer.echo(
                    yaml.dump(
                        pr.model_dump(), default_flow_style=False, allow_unicode=True
                    )
                )
            else:
                render_pr_created(pr)
