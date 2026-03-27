"""PR lifecycle commands (ready).

Note: merge command has been removed from public CLI.
Merge is now handled by flow done / integrate, not pr merge.
"""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.pr_helpers import noop_context
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.pr_ready_usecase import PrReadyUsecase
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_ready


def _run_ready_gates(pr_number: int, yes: bool) -> None:
    """Run command-scoped PR ready quality gates."""
    from rich.console import Console

    from vibe3.commands.pr_quality_gates import run_coverage_gate, run_risk_gate

    console = Console()
    run_coverage_gate(console, yes)
    run_risk_gate(console, pr_number)


def _build_pr_ready_usecase() -> PrReadyUsecase:
    """Construct PR ready usecase with command-local dependencies."""
    return PrReadyUsecase(
        pr_service=PRService(),
        gate_runner=_run_ready_gates,
        confirmer=lambda pr_number: typer.confirm(
            "Mark PR #"
            f"{pr_number} as ready for review? (draft -> ready, irreversible)"
        ),
    )


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register pr lifecycle commands."""

    @app.command()
    def ready(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        yes: Annotated[
            bool, typer.Option("-y", "--yes", help="绕过业务逻辑检查并自动确认")
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
        """Mark PR as ready with quality gates.

        质量门禁检查:
        - 覆盖率检查（分层覆盖率统计）
        - 风险评分检查（来自 inspect pr）

        使用 --yes 绕过业务逻辑检查（覆盖率不足等）并自动确认.
        """
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
            logger.bind(command="pr ready", pr_number=pr_number, yes=yes).info(
                "Marking PR as ready for review"
            )

            try:
                pr = _build_pr_ready_usecase().mark_ready(pr_number=pr_number, yes=yes)
            except RuntimeError as error:
                if str(error) == "aborted by user":
                    logger.info("Aborted by user")
                    raise typer.Exit(0) from None
                raise

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
