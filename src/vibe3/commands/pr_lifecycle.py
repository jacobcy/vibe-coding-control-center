"""PR lifecycle commands (ready, merge)."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.pr_helpers import noop_context
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_merged, render_pr_ready


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register pr lifecycle commands."""

    @app.command()
    def ready(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        yes: Annotated[
            bool, typer.Option("-y", "--yes", help="自动确认（跳过交互）")
        ] = False,  # noqa: E501
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
        """Mark PR as ready for review."""
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        ctx = (
            trace_context(command="pr ready", domain="pr", pr_number=pr_number)
            if trace
            else noop_context()
        )
        with ctx:
            logger.bind(command="pr ready", pr_number=pr_number).info(
                "Marking PR as ready for review"
            )

            if not yes:
                confirmed = typer.confirm(
                    "Mark PR #"
                    f"{pr_number} as ready for review? (draft → ready, irreversible)"
                )
                if not confirmed:
                    logger.info("Aborted by user")
                    raise typer.Exit(0)

            service = PRService()
            pr = service.mark_ready(pr_number)

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
                render_pr_ready(pr)

    @app.command()
    def merge(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        yes: Annotated[
            bool, typer.Option("-y", "--yes", help="自动确认（跳过交互）")
        ] = False,  # noqa: E501
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
        """Merge PR."""
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        ctx = (
            trace_context(command="pr merge", domain="pr", pr_number=pr_number)
            if trace
            else noop_context()
        )
        with ctx:
            logger.bind(command="pr merge", pr_number=pr_number).info("Merging PR")

            if not yes:
                confirmed = typer.confirm(f"Merge PR #{pr_number}? (irreversible)")
                if not confirmed:
                    logger.info("Aborted by user")
                    raise typer.Exit(0)

            service = PRService()
            pr = service.merge_pr(pr_number)

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
                render_pr_merged(pr)
