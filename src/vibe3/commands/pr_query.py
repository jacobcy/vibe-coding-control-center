"""PR query commands.

Public commands:
- show: Show PR details with change analysis

Removed from public CLI:
- version-bump: No clear project packaging value
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Callable

import typer
from loguru import logger
from rich.console import Console

from vibe3.agents.review_pipeline_helpers import run_inspect_json
from vibe3.analysis.inspect_output_adapter import (
    as_list,
    dag,
    impact,
    pr_analysis_summary,
    score,
)
from vibe3.analysis.local_review_report import (
    LocalReviewReport,
    find_latest_prepush_report,
)
from vibe3.commands.output_format import (
    add_execution_step,
    create_trace_output,
    output_result,
)
from vibe3.commands.pr_helpers import noop_context
from vibe3.models.pr import PRResponse
from vibe3.models.trace import TraceOutput
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_local_review_summary, render_pr_details


@dataclass(frozen=True)
class PrQueryTarget:
    """Resolved PR query target from explicit args or current flow."""

    pr_number: int | None
    branch: str | None
    current_branch: str | None
    from_flow: bool = False


def _resolve_pr_target(
    pr_svc: PRService,
    pr_number: int | None,
    branch: str | None,
) -> PrQueryTarget:
    """Resolve explicit target or infer PR number from current flow."""
    if pr_number or branch:
        return PrQueryTarget(
            pr_number=pr_number,
            branch=branch,
            current_branch=None,
            from_flow=False,
        )

    current_branch = pr_svc.git_client.get_current_branch()
    try:
        pr = pr_svc.github_client.get_pr(None, current_branch)
        resolved_pr = pr.number if pr else None
    except Exception:
        resolved_pr = None

    return PrQueryTarget(
        pr_number=resolved_pr,
        branch=None,
        current_branch=current_branch,
        from_flow=resolved_pr is not None,
    )


def _fetch_pr_or_raise(
    pr_svc: PRService,
    pr_number: int | None,
    branch: str | None,
    *,
    current_branch: str | None = None,
) -> "PRResponse":
    """Load PR or raise a command-facing lookup error."""
    pr = pr_svc.get_pr(pr_number, branch)
    if not pr and pr_number is not None and current_branch:
        pr = pr_svc.get_pr(branch=current_branch)
    if not pr:
        raise LookupError("PR not found")
    return pr


def _build_missing_pr_message(
    pr_svc: PRService,
    *,
    pr_number: int | None,
    branch: str | None,
    current_branch: str | None,
) -> str:
    """Build a command-facing not-found message."""
    if not pr_number and not branch:
        branch_name = current_branch or pr_svc.git_client.get_current_branch()
        flow_status = FlowService(store=pr_svc.store).get_flow_status(branch_name)
        bind_hint = ""
        if not flow_status or flow_status.task_issue_number is None:
            bind_hint = (
                "\n提示：当前 flow 还没有 task，建议先执行\n"
                "  vibe3 flow bind <issue> --role task"
            )
        return (
            f"No PR found for current branch '{branch_name}'\n\n"
            "To create a PR, run:\n"
            f'  vibe3 pr create -t "Your PR title"{bind_hint}'
        )

    target = f"PR #{pr_number}" if pr_number else f"branch '{branch}'"
    return f"{target} not found"


def _load_pr_analysis_summary(
    pr_number: int,
    inspect_runner: Callable[[list[str]], dict[str, object]],
) -> dict[str, Any]:
    """Load inspect summary used by command outputs."""
    analysis = inspect_runner(["pr", str(pr_number)])
    return pr_analysis_summary(analysis)


def _fetch_and_record_external_events(
    pr_number: int,
    branch: str,
    github_client: Any,
    handoff_svc: HandoffService,
) -> None:
    """Fetch CI status and comments from GitHub, record as external events.

    This is a best-effort operation - failures are logged but not raised.

    Args:
        pr_number: PR number
        branch: Branch name
        github_client: GitHub client with list_pr_comments/list_pr_review_comments
        handoff_svc: Handoff service for recording events
    """
    try:
        # Fetch CI status (already in PRResponse, but we need to fetch it)
        # Note: We could pass it from the caller, but re-fetching ensures fresh data
        pr = github_client.get_pr(pr_number, None)
        if pr and pr.ci_status:
            handoff_svc.record_ci_status(
                branch=branch,
                pr_number=pr_number,
                status=pr.ci_status,
            )

        # Fetch general comments
        comments = []
        try:
            comments = github_client.list_pr_comments(pr_number)
        except Exception as e:
            logger.bind(
                domain="pr",
                action="fetch_comments",
                pr_number=pr_number,
            ).warning(f"Failed to fetch PR comments: {e}")

        # Fetch review comments
        review_comments = []
        try:
            review_comments = github_client.list_pr_review_comments(pr_number)
        except Exception as e:
            logger.bind(
                domain="pr",
                action="fetch_review_comments",
                pr_number=pr_number,
            ).warning(f"Failed to fetch PR review comments: {e}")

        # Record comments
        if comments or review_comments:
            handoff_svc.record_pr_comments(
                branch=branch,
                pr_number=pr_number,
                comments=comments,
                review_comments=review_comments,
            )

    except Exception as e:
        logger.bind(
            domain="pr",
            action="record_external_events",
            pr_number=pr_number,
            branch=branch,
        ).warning(f"Failed to record external events: {e}")


def _build_pr_output_payload(
    pr: "PRResponse",
    analysis_summary: dict[str, Any] | None = None,
    local_review: "LocalReviewReport | None" = None,
) -> dict[str, Any]:
    """Merge PR data with optional analysis summary and local review.

    Args:
        pr: PR response data
        analysis_summary: Optional analysis summary from inspect
        local_review: Optional local review report data

    Returns:
        Dictionary with merged payload for structured output
    """
    payload = pr.model_dump()
    if analysis_summary:
        payload["analysis"] = {
            key: value for key, value in analysis_summary.items() if key != "raw"
        }
    if local_review:
        payload["local_review"] = {
            "risk_level": local_review.risk_level,
            "risk_score": local_review.risk_score,
            "verdict": local_review.verdict,
            "report_path": str(local_review.report_path),
            "created_at": (
                local_review.created_at.isoformat() if local_review.created_at else None
            ),
        }
    return payload


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

            pr_svc = PRService()
            target = _resolve_pr_target(pr_svc, pr_number, branch)
            pr_number = target.pr_number
            branch = target.branch
            if target.from_flow and target.current_branch is not None:
                logger.bind(
                    branch=target.current_branch,
                    pr_number=pr_number,
                ).debug("Found PR number in flow state")

            try:
                pr = _fetch_pr_or_raise(
                    pr_svc,
                    pr_number,
                    branch,
                    current_branch=target.current_branch,
                )
            except LookupError:
                typer.echo(
                    _build_missing_pr_message(
                        pr_svc,
                        pr_number=pr_number,
                        branch=branch,
                        current_branch=target.current_branch,
                    ),
                    err=True,
                )
                raise typer.Exit(1) from None

            # Record external events (best-effort, non-blocking)
            try:
                if pr and pr_number:
                    effective_branch = branch or target.current_branch
                    if effective_branch:
                        _fetch_and_record_external_events(
                            pr_number=pr_number,
                            branch=effective_branch,
                            github_client=pr_svc.github_client,
                            handoff_svc=HandoffService(store=pr_svc.store),
                        )
            except Exception as exc:
                logger.bind(domain="pr", action="record_external_events").warning(
                    f"Failed to record external events: {exc}"
                )

            analysis_summary = None
            if pr_number:
                analysis_summary = _load_pr_analysis_summary(
                    pr_number, run_inspect_json
                )
                logger.debug("Successfully retrieved change analysis")

            # Find local pre-push review report
            local_review = find_latest_prepush_report()
            if local_review:
                logger.debug(
                    f"Found local review report: {local_review.report_path.name}"
                )

            if trace_output or json_output or yaml_output:
                result = _build_pr_output_payload(pr, analysis_summary, local_review)
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

                # Show local review summary
                render_local_review_summary(local_review)
