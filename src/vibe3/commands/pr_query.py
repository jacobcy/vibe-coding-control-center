"""PR query commands.

Public commands:
- show: Show PR details with change analysis

Removed from public CLI:
- version-bump: No clear project packaging value
"""

from datetime import datetime
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console

from vibe3.commands.output_format import (
    add_execution_step,
    create_trace_output,
    output_result,
)
from vibe3.commands.pr_helpers import noop_context
from vibe3.models.trace import TraceOutput
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.inspect_output_adapter import as_list, dag, impact, score
from vibe3.services.pr_query_usecase import PrQueryUsecase
from vibe3.services.pr_service import PRService
from vibe3.services.review_pipeline_helpers import run_inspect_json
from vibe3.ui.pr_ui import render_pr_details


def _build_pr_query_usecase() -> PrQueryUsecase:
    """Construct PR query usecase with command-local dependencies."""
    service = PRService()
    return PrQueryUsecase(
        pr_service=service,
        flow_service=FlowService(),
        inspect_runner=run_inspect_json,
    )


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
        ] = False,
        yaml_output: Annotated[
            bool, typer.Option("--yaml", help="YAML 格式输出")
        ] = False,
    ) -> None:
        """Show PR details with change analysis."""
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

            usecase = _build_pr_query_usecase()
            target = usecase.resolve_target(pr_number, branch)
            pr_number = target.pr_number
            branch = target.branch
            if target.from_flow and target.current_branch is not None:
                logger.bind(
                    branch=target.current_branch,
                    pr_number=pr_number,
                ).debug("Found PR number in flow state")

            try:
                pr = usecase.fetch_pr(
                    pr_number,
                    branch,
                    current_branch=target.current_branch,
                )
            except LookupError:
                typer.echo(
                    usecase.build_missing_pr_message(
                        pr_number=pr_number,
                        branch=branch,
                        current_branch=target.current_branch,
                    ),
                    err=True,
                )
                raise typer.Exit(1) from None

            analysis_summary = None
            if pr_number:
                analysis_summary = usecase.load_analysis_summary(pr_number)
                logger.debug("Successfully retrieved change analysis")

            if trace_output or json_output or yaml_output:
                result = usecase.build_output_payload(pr, analysis_summary)
                output_result(
                    result=result,
                    trace_output=trace_output,
                    json_output=json_output,
                    yaml_output=yaml_output,
                )
            else:
                # Human-readable output
                render_pr_details(pr)

                # Show change analysis
                if analysis_summary:
                    analysis = analysis_summary.get("raw")
                    if not isinstance(analysis, dict):
                        analysis = {}

                    console = Console()

                    console.print("\n[bold]### Change Analysis[/]")
                    score_items = score(analysis)
                    console.print(
                        f"- [cyan]Risk Level[/]: {score_items.get('level', 'N/A')}"
                    )
                    console.print(
                        f"- [cyan]Risk Score[/]: {score_items.get('score', 'N/A')}"
                    )
                    reason = score_items.get("reason")
                    if reason:
                        console.print(f"- [cyan]Reason[/]: {reason}")
                    trigger_factors = as_list(score_items.get("trigger_factors"))
                    if trigger_factors:
                        console.print("- [cyan]Trigger Factors[/]:")
                        for factor in trigger_factors:
                            console.print(f"  - {factor}")

                    impact_items = impact(analysis)
                    changed_files = as_list(impact_items.get("changed_files"))
                    console.print(f"- [cyan]Changed Files[/]: {len(changed_files)}")

                    dag_items = dag(analysis)
                    impacted_modules = as_list(dag_items.get("impacted_modules"))
                    console.print(
                        f"- [cyan]Impacted Modules[/]: {len(impacted_modules)}"
                    )
                    recommendations = as_list(score_items.get("recommendations"))
                    if recommendations:
                        console.print("- [cyan]Recommendations[/]:")
                        for item in recommendations:
                            console.print(f"  - {item}")

                    # Show top changed files
                    if changed_files:
                        console.print("\n[bold]### Top Changed Files[/]")
                        for file in changed_files[:5]:
                            console.print(f"  - {file}")
