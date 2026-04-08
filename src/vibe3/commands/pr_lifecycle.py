"""PR lifecycle commands (ready).

Note: merge command has been removed from public CLI.
Merge is now handled by flow done / integrate, not pr merge.
"""

import json
from typing import Annotated, List

import typer
from loguru import logger

from vibe3.commands.pr_helpers import noop_context
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_ready_usecase import PrReadyAbortedError, PrReadyUsecase
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_ready


def _build_pr_ready_usecase(pr_service: PRService | None = None) -> PrReadyUsecase:
    """Construct PR ready usecase with command-local dependencies."""
    return PrReadyUsecase(
        pr_service=pr_service or PRService(),
        confirmer=lambda pr_number: typer.confirm(
            "Mark PR #"
            f"{pr_number} as ready for review? (draft -> ready, irreversible)"
        ),
    )


def _resolve_ready_pr_number(
    pr_number: int | None,
    *,
    pr_service: PRService,
    flow_service: FlowService,
) -> int:
    """Resolve ready target PR number from arg or current flow context."""
    if pr_number is not None:
        return pr_number

    branch = flow_service.get_current_branch()
    flow_data = pr_service.store.get_flow_state(branch)
    if flow_data and flow_data.get("pr_number") is not None:
        return int(flow_data["pr_number"])

    pr = pr_service.get_pr(branch=branch)
    if pr is not None:
        return pr.number

    raise RuntimeError(
        f"No PR found for current branch '{branch}'.\n"
        "可显式指定：vibe3 pr ready <PR_NUMBER>"
    )


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register pr lifecycle commands."""

    @app.command()
    def ready(
        pr_number: Annotated[int | None, typer.Argument(help="PR number")] = None,
        yes: Annotated[
            bool, typer.Option("-y", "--yes", help="自动确认并发布 PR")
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
        review: Annotated[
            List[str] | None,
            typer.Option(
                "--review",
                help="Request AI review (codex, copilot, auggie, claude)",
            ),
        ] = None,
    ) -> None:
        """Mark PR as ready for review.

        此操作会将 PR 从 draft 状态转换为 ready 状态，并触发 reviewer briefing 生成。
        本地质量门禁已移至 pre-push 钩子。
        """
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        pr_service = PRService()
        flow_service = FlowService()
        try:
            target_pr_number = _resolve_ready_pr_number(
                pr_number,
                pr_service=pr_service,
                flow_service=flow_service,
            )
        except RuntimeError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

        ctx = (
            trace_context(command="pr ready", domain="pr", pr_number=target_pr_number)
            if trace
            else noop_context()
        )
        with ctx:
            logger.bind(command="pr ready", pr_number=target_pr_number, yes=yes).info(
                "Marking PR as ready for review"
            )

            try:
                pr = _build_pr_ready_usecase(pr_service=pr_service).mark_ready(
                    pr_number=target_pr_number, yes=yes, requested_reviewers=review
                )
            except PrReadyAbortedError:
                logger.info("Aborted by user")
                raise typer.Exit(0) from None

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
                render_pr_ready(pr, requested_reviewers=review)
