"""PR creation commands."""

import json
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.prompt import Prompt

from vibe3.commands.pr_helpers import noop_context
from vibe3.config.settings import VibeConfig
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.ai_service import AIService
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_created


def _get_commits(base_branch: str = "main") -> list[str]:
    """Get commit messages between current branch and base.

    Args:
        base_branch: Base branch name

    Returns:
        List of commit messages
    """
    try:
        result = subprocess.run(
            ["git", "log", f"{base_branch}..HEAD", "--oneline", "--format=%s"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        ]
    except subprocess.CalledProcessError:
        return []


def _get_changed_files(base_branch: str = "main") -> list[str]:
    """Get list of changed files between current branch and base.

    Args:
        base_branch: Base branch name

    Returns:
        List of changed file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        ]
    except subprocess.CalledProcessError:
        return []


def register_create_command(app: typer.Typer) -> None:
    """Register pr create command."""

    @app.command()
    def create(
        title: Annotated[str, typer.Option("-t", help="PR title")] = "",
        body: Annotated[str, typer.Option("-b", help="PR description")] = "",
        base: Annotated[str, typer.Option(help="Base branch")] = "main",
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
            logger.bind(command="pr create", title=title, base=base).info("Creating PR")

            pr_title = title
            pr_body = body

            if ai and not title:
                console = Console()
                commits = _get_commits(base)
                changed_files = _get_changed_files(base)

                if not commits:
                    console.print(
                        "[yellow]No commits found, cannot generate AI suggestions[/]"
                    )
                else:
                    config = VibeConfig.get_defaults()
                    prompts_path = Path("config/prompts.yaml")
                    ai_service = AIService(config.ai, prompts_path=prompts_path)
                    result = ai_service.suggest_pr_content(commits, changed_files)

                    if result:
                        suggested_title, suggested_body = result
                        if suggested_title:
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
                        if suggested_body:
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
                        console.print(
                            "[yellow]AI suggestion unavailable, using manual input[/]"
                        )

            if not pr_title:
                pr_title = Prompt.ask("Enter PR title")

            service = PRService()
            pr = service.create_draft_pr(title=pr_title, body=pr_body, base_branch=base)

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
