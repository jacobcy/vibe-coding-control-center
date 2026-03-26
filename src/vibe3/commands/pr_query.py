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
from vibe3.commands.review_helpers import run_inspect_json
from vibe3.models.trace import TraceOutput
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_details


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

            service = PRService()

            # If no pr_number or branch provided, try to get from flow
            current_branch: str | None = None
            if not pr_number and not branch:
                flow_service = FlowService()
                current_branch = flow_service.get_current_branch()
                flow_data = service.store.get_flow_state(current_branch)
                if flow_data and flow_data.get("pr_number"):
                    pr_number = flow_data["pr_number"]
                    logger.bind(branch=current_branch, pr_number=pr_number).debug(
                        "Found PR number in flow state"
                    )

            pr = service.get_pr(pr_number, branch)

            if not pr:
                # Get current branch for better error message
                if not pr_number and not branch:
                    if current_branch is None:
                        current_branch = FlowService().get_current_branch()
                    flow_status = FlowService().get_flow_status(current_branch)
                    bind_hint = ""
                    if not flow_status or flow_status.task_issue_number is None:
                        bind_hint = (
                            "\n提示：当前 flow 还没有 task，建议先执行\n"
                            "  vibe3 flow bind <issue> --role task"
                        )
                    typer.echo(
                        f"No PR found for current branch '{current_branch}'\n\n"
                        "To create a PR, run:\n"
                        f'  vibe3 pr create -t "Your PR title"{bind_hint}',
                        err=True,
                    )
                else:
                    target = f"PR #{pr_number}" if pr_number else f"branch '{branch}'"
                    typer.echo(f"{target} not found", err=True)
                raise typer.Exit(1)

            # Get change analysis if pr_number is provided
            analysis = None
            if pr_number:
                # Fail-fast: if analysis fails, immediately throw
                analysis = run_inspect_json(["pr", str(pr_number)])
                logger.debug("Successfully retrieved change analysis")

            if trace_output or json_output or yaml_output:
                # Merge basic info and analysis results
                result = pr.model_dump()
                if analysis:
                    score_data = analysis.get("score", {})  # type: ignore[attr-defined]
                    impact_data = analysis.get("impact", {})  # type: ignore[attr-defined]
                    dag_data = analysis.get("dag", {})  # type: ignore[attr-defined]

                    result["analysis"] = {
                        "risk_level": score_data.get("level"),  # type: ignore[attr-defined]
                        "risk_score": score_data.get("score"),  # type: ignore[attr-defined]
                        "changed_files_count": len(
                            impact_data.get("changed_files", [])  # type: ignore[attr-defined]
                        ),
                        "impacted_modules_count": len(
                            dag_data.get("impacted_modules", [])  # type: ignore[attr-defined]
                        ),
                    }
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
                if analysis:
                    console = Console()

                    console.print("\n[bold]### Change Analysis[/]")
                    score = analysis.get("score", {})  # type: ignore[attr-defined]
                    console.print(f"- [cyan]Risk Level[/]: {score.get('level', 'N/A')}")  # type: ignore[attr-defined]
                    console.print(f"- [cyan]Risk Score[/]: {score.get('score', 'N/A')}")  # type: ignore[attr-defined]
                    reason = score.get("reason")  # type: ignore[attr-defined]
                    if reason:
                        console.print(f"- [cyan]Reason[/]: {reason}")
                    trigger_factors = score.get("trigger_factors", [])  # type: ignore[attr-defined]
                    if trigger_factors:
                        console.print("- [cyan]Trigger Factors[/]:")
                        for factor in trigger_factors:
                            console.print(f"  - {factor}")

                    impact = analysis.get("impact", {})  # type: ignore[attr-defined]
                    changed_files = impact.get("changed_files", [])  # type: ignore[attr-defined]
                    console.print(f"- [cyan]Changed Files[/]: {len(changed_files)}")

                    dag = analysis.get("dag", {})  # type: ignore[attr-defined]
                    impacted_modules = dag.get("impacted_modules", [])  # type: ignore[attr-defined]
                    console.print(
                        f"- [cyan]Impacted Modules[/]: {len(impacted_modules)}"
                    )
                    recommendations = score.get("recommendations", [])  # type: ignore[attr-defined]
                    if recommendations:
                        console.print("- [cyan]Recommendations[/]:")
                        for item in recommendations:
                            console.print(f"  - {item}")

                    # Show top changed files
                    if changed_files:
                        console.print("\n[bold]### Top Changed Files[/]")
                        for file in changed_files[:5]:
                            console.print(f"  - {file}")
