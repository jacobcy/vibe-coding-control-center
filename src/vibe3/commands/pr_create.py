"""PR creation commands."""

import json
import os
import sys
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.pr_helpers import build_base_resolution_usecase, noop_context
from vibe3.models.pr import PRResponse
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_create_usecase import PRCreateUsecase
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_created


def _is_interactive(json_output: bool, yaml_output: bool) -> bool:
    return (
        not json_output
        and not yaml_output
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    )


def _emit_pr_result(pr: PRResponse, json_output: bool, yaml_output: bool) -> None:
    """Render PR creation result in the requested format."""
    if json_output:
        typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
    elif yaml_output:
        import yaml

        typer.echo(
            yaml.dump(pr.model_dump(), default_flow_style=False, allow_unicode=True)
        )
    else:
        render_pr_created(pr)


def _resolve_branch_for_ai_context(current_branch: str) -> str:
    """Normalize detached HEAD in CI to PR head branch when available."""
    if current_branch != "HEAD":
        return current_branch
    return os.getenv("GITHUB_HEAD_REF", current_branch)


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
        yes: Annotated[
            bool,
            typer.Option("--yes", "-y", help="Bypass missing-task guard"),
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
            flow_service = FlowService()
            branch = _resolve_branch_for_ai_context(
                flow_service.get_current_branch()
            )
            resolved_base = base_resolver.resolve_pr_create_base(base)
            logger.bind(command="pr create", title=title, base=resolved_base).info(
                "Creating PR"
            )
            interactive = _is_interactive(json_output, yaml_output)

            usecase = PRCreateUsecase(
                flow_service=flow_service,
                base_resolver=base_resolver,
            )
            pr_service = PRService()

            existing_pr = pr_service.get_pr(branch=branch)
            if existing_pr is not None:
                pr_service.sync_pr_state_from_remote(existing_pr, actor="server")
                _emit_pr_result(existing_pr, json_output, yaml_output)
                return

            try:
                usecase.check_flow_task(branch, yes=yes)
            except RuntimeError as error:
                typer.echo(str(error), err=True)
                raise typer.Exit(1) from error

            ai_title, ai_body = ("", "")
            if ai and not title:
                ai_title, ai_body = usecase.suggest_content(
                    branch, resolved_base, interactive
                )

            try:
                pr_title = usecase.resolve_title(title, ai_title, interactive)
            except ValueError:
                typer.echo("Error: PR title is required", err=True)
                raise typer.Exit(1)

            pr_body = ai_body if ai_body else body
            actor = "ai_assistant" if ai else "server"

            pr = pr_service.create_draft_pr(
                title=pr_title,
                body=pr_body,
                base_branch=resolved_base,
                actor=actor,
            )

            _emit_pr_result(pr, json_output, yaml_output)
