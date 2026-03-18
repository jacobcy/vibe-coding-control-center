"""PR query commands."""

from datetime import datetime
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.output_format import (
    add_execution_step,
    create_trace_output,
    output_result,
)
from vibe3.commands.pr_helpers import noop_context
from vibe3.models.trace import TraceOutput
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_details, render_version_bump


def register_query_commands(app: typer.Typer) -> None:
    """Register pr query commands."""

    @app.command()
    def show(
        pr_number: Annotated[int | None, typer.Argument(help="PR number")] = None,
        branch: Annotated[str | None, typer.Option("-b", help="Branch name")] = None,
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
        """Show PR details."""
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        trace_output: TraceOutput | None = None
        start_time = datetime.now()

        if trace:
            trace_output = create_trace_output("pr show", start_time)

        ctx = trace_context(command="pr show", domain="pr") if trace else noop_context()
        with ctx:
            logger.bind(command="pr show", pr_number=pr_number, branch=branch).info(
                "Fetching PR details"
            )

            if trace_output:
                add_execution_step(
                    trace_output,
                    time=start_time.strftime("%H:%M:%S"),
                    level="INFO",
                    module="vibe3.commands.pr",
                    function="show",
                    line=99,
                    message="Fetching PR details",
                )

            service = PRService()
            pr = service.get_pr(pr_number, branch)

            if not pr:
                logger.error("PR not found")
                raise typer.Exit(1)

            if trace_output or json_output or yaml_output:
                output_result(
                    result=pr.model_dump(),
                    trace_output=trace_output,
                    json_output=json_output,
                    yaml_output=yaml_output,
                )
            else:
                render_pr_details(pr)

    @app.command()
    def version_bump(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        group: Annotated[str | None, typer.Option("-g", help="Task group")] = None,
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
        """Calculate version bump for PR."""
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        ctx = (
            trace_context(command="pr version-bump", domain="pr", pr_number=pr_number)
            if trace
            else noop_context()
        )
        with ctx:
            logger.bind(
                command="pr version-bump", pr_number=pr_number, group=group
            ).info("Calculating version bump")

            service = PRService()
            response = service.calculate_version_bump(pr_number, group)

            if json_output:
                import json

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
                render_version_bump(response)
