"""PR review command."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.pr_helpers import noop_context
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_review


def register_review_command(app: typer.Typer) -> None:
    """Register pr review command."""

    @app.command()
    def review(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        publish: Annotated[bool, typer.Option(help="Publish review as comment")] = True,
        trace: Annotated[
            bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="JSON 格式输出")
        ] = False,  # noqa: E501
        yaml_output: Annotated[
            bool, typer.Option("--yaml", help="YAML 格式输出")
        ] = False,  # noqa: E501
    ) -> None:
        """Review PR using local LLM (codex)."""
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        ctx = (
            trace_context(command="pr review", domain="pr", pr_number=pr_number)
            if trace
            else noop_context()
        )
        with ctx:
            logger.bind(command="pr review", pr_number=pr_number, publish=publish).info(
                "Reviewing PR"
            )

            service = PRService()
            response = service.review_pr(pr_number, publish)

            if json_output:
                typer.echo(json.dumps(response.model_dump(), indent=2, default=str))
            elif yaml_output:
                import yaml

                typer.echo(
                    yaml.dump(
                        response.model_dump(),
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                )
            else:
                render_pr_review(response)
