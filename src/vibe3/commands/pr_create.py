"""PR creation commands."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.pr_helpers import noop_context
from vibe3.models.pr import PRMetadata
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_created


def register_create_command(app: typer.Typer) -> None:
    """Register pr create command."""

    @app.command()
    def create(
        title: Annotated[str, typer.Option("-t", help="PR title")],
        body: Annotated[str, typer.Option("-b", help="PR description")] = "",
        base: Annotated[str, typer.Option(help="Base branch")] = "main",
        task: Annotated[int | None, typer.Option(help="Task issue #")] = None,
        flow: Annotated[str | None, typer.Option(help="Flow slug")] = None,
        spec: Annotated[str | None, typer.Option(help="Spec reference")] = None,
        planner: Annotated[str | None, typer.Option(help="Planner agent")] = None,
        executor: Annotated[str | None, typer.Option(help="Executor agent")] = None,
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
        """Create draft PR."""
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

            service = PRService()
            metadata = None
            if any([task, flow, spec, planner, executor]):
                metadata = PRMetadata(
                    task_issue=task,
                    flow_slug=flow,
                    spec_ref=spec,
                    planner=planner,
                    executor=executor,
                )

            pr = service.create_draft_pr(
                title=title, body=body, base_branch=base, metadata=metadata
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
