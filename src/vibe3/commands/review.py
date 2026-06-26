"""Review command - Code review layer using inspect context and codeagent-wrapper."""

from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.commands.command_options import (
    _AGENT_OPT,
    _ASYNC_OPT,
    _BACKEND_OPT,
    _DRY_RUN_OPT,
    _FRESH_SESSION_OPT,
    _MODEL_OPT,
    _SHOW_PROMPT_OPT,
    _TRACE_OPT,
    ensure_flow_for_current_branch,
    load_config_and_validate_model,
    validate_show_prompt_dependency,
)
from vibe3.commands.common import enable_method_trace
from vibe3.commands.pr_helpers import build_base_resolution_usecase
from vibe3.exceptions import UserError
from vibe3.roles import (
    ReviewRunResult,
    build_base_review_request,
    validate_review_prerequisites,
)
from vibe3.services.flow import FlowService, resolve_branch_arg
from vibe3.ui import display_codeagent_result

app = typer.Typer(
    name="review",
    help="Code review with two modes:\n\n"
    "  --branch <b> - Review issue implementation (orchestra-driven)\n"
    "  base [branch] - Review local changes vs base branch (compares snapshots)",
    rich_markup_mode="rich",
)

BranchOption = Annotated[
    str | None,
    typer.Option("--branch", "-b", help="Branch name or issue number (e.g., 320)"),
]

_YES_OPT = Annotated[
    bool,
    typer.Option(
        "--yes",
        "-y",
        help="Skip gate checks (report_ref, empty changes)",
    ),
]


def _emit_review_result(result: ReviewRunResult, report_ref: str | None = None) -> None:
    """Render review result summary using shared display_codeagent_result.

    Metadata (backend/model/log/tmux) goes through the shared display path
    used by plan/run. Review-specific verdict and handoff file are shown on top.

    report_ref is resolved from flow state (the run report being reviewed)
    and passed through the shared metadata channel so it appears alongside
    backend/model/log/tmux in the same section as plan/run.
    """
    from rich.console import Console

    from vibe3.agents import CodeagentResult

    console = Console()

    # Unified metadata display — same channel as plan/run
    display_codeagent_result(
        console,
        CodeagentResult(
            success=result.verdict not in {"ERROR", "UNKNOWN"},
            backend=result.backend,
            model=result.model,
            report_ref=report_ref,
            tmux_session=result.tmux_session,
            log_path=result.log_path,
        ),
        "Review",
    )

    # Review-specific: verdict and handoff file
    if result.verdict not in {"ASYNC", "DRY_RUN"}:
        console.print(f"\n=== Verdict: {result.verdict} ===")
        if result.handoff_file:
            console.print(f"[cyan]-> Review saved to:[/cyan] {result.handoff_file}")


def _resolve_report_ref(branch: str | None) -> str | None:
    """Get report_ref from flow state, or None if unavailable.

    report_ref is set by vibe3 run (the run report). Review needs it to
    tell the user which run report is being reviewed.
    """
    from vibe3.services.flow import resolve_flow_ref

    return resolve_flow_ref(branch, "report_ref")


def _check_report_ref(branch: str) -> bool:
    """Check if run report exists for the given branch flow.

    Returns True if report_ref exists, False otherwise.
    Only applicable for manual review path (orchestra skips this).
    """
    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)
    if flow and flow.report_ref:
        return True
    return False


def _review_branch_impl(
    branch: str,
    trace: bool,
    dry_run: bool,
    no_async: bool,
    show_prompt: bool,
    yes: bool = False,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
) -> None:
    """Review implementation for a branch via role sync runner."""
    if trace:
        enable_method_trace()

    # Register EDA event handlers for review command
    from vibe3.domain import register_event_handlers
    from vibe3.models import ManualReviewIntent, publish_and_wait

    register_event_handlers()

    # Load config and validate --model requires backend (CLI or config)
    # config is unused here but returned for potential future use
    _config = load_config_and_validate_model("review", agent, backend, model)

    flow_service = FlowService()
    try:
        _, issue_number = validate_review_prerequisites(flow_service, branch)
    except UserError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    # Gate check: report_ref must exist (unless --yes or orchestra path)
    if not yes and not _check_report_ref(branch):
        typer.echo(
            "No execution report found (report_ref is empty). "
            "Run 'vibe3 run --branch <b>' first, or use --yes to skip this check.",
            err=True,
        )
        raise typer.Exit(1)

    # Publish ManualReviewIntent event and wait for result
    result = publish_and_wait(
        ManualReviewIntent(
            issue_number=issue_number,
            branch=branch,
            is_base_review=False,
            dry_run=dry_run,
            no_async=no_async,
            show_prompt=show_prompt,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
        )
    )

    # Display result
    if result is None:
        typer.echo("Review dispatched (async mode)")
    else:
        report_ref = _resolve_report_ref(branch)
        _emit_review_result(result, report_ref)


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    branch: BranchOption = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
    yes: _YES_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
    fresh_session: _FRESH_SESSION_OPT = False,
) -> None:
    """Review with --branch for orchestra-driven review, or use base subcommand."""
    if ctx.invoked_subcommand is not None:
        return

    target_branch = resolve_branch_arg(branch)

    # Validate --show-prompt requires --dry-run
    validate_show_prompt_dependency(dry_run, show_prompt)

    _review_branch_impl(
        branch=target_branch,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
        yes=yes,
        agent=agent,
        backend=backend,
        model=model,
        fresh_session=fresh_session,
    )


@app.command(name="issue", hidden=True)
def issue_command(
    issue: Annotated[int, typer.Argument(help="GitHub issue number")],
    ctx: typer.Context,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
    yes: _YES_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
    fresh_session: _FRESH_SESSION_OPT = False,
) -> None:
    """Legacy alias: review --branch <issue>."""
    default(
        ctx=ctx,
        branch=str(issue),
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
        yes=yes,
        agent=agent,
        backend=backend,
        model=model,
        fresh_session=fresh_session,
    )


@app.command(name="base")
def base(
    base_branch: Annotated[
        str | None,
        typer.Argument(
            help="Base branch to compare against (auto-detected if not specified)"
        ),
    ] = None,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Custom prompt (skips context building)"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
    yes: _YES_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
    fresh_session: _FRESH_SESSION_OPT = False,
) -> None:
    """Review local branch changes against a base branch (compares codebase snapshots).

    This command compares your current local branch state against a base branch.
    It analyzes:
    - Structure diff (file/module/dependency changes)
    - Changed symbols (function-level impact)
    - Impacted modules (DAG upstream dependencies)

    If base_branch is not specified, it will auto-detect the closest parent branch
    (e.g., for refactor/B forked from feature/A, it will compare against feature/A
    instead of main).

    Use this to review local changes before pushing or creating a PR.

    Example: vibe3 review base origin/main "Focus on behavior changes"
    """
    if trace:
        enable_method_trace()

    # Validate --show-prompt requires --dry-run
    validate_show_prompt_dependency(dry_run, show_prompt)

    # Register EDA event handlers for review command
    from vibe3.domain import register_event_handlers
    from vibe3.models import ManualReviewIntent, publish_and_wait

    register_event_handlers()

    # Load config and validate --model requires backend (CLI or config)
    # config is unused here but returned for potential future use
    _config = load_config_and_validate_model("review", agent, backend, model)

    flow_service, current_branch = ensure_flow_for_current_branch()

    # Get creation_source from flow state if available
    flow_state = flow_service.get_flow_status(current_branch)
    creation_source = flow_state.creation_source if flow_state else None

    try:
        resolved_base = build_base_resolution_usecase().resolve_review_base(
            base_branch,
            current_branch=current_branch,
            creation_source=creation_source,
        )
    except UserError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if resolved_base.auto_detected:
        typer.echo(f"-> Auto-detected parent branch: {resolved_base.base_branch}")

    log = logger.bind(
        domain="review",
        action="base",
        current_branch=current_branch,
        base_branch=resolved_base.base_branch,
    )
    log.info("Starting branch review")
    typer.echo(f"-> Review: {current_branch} vs {resolved_base.base_branch}")

    # Gate check: warn if no changes detected (unless --yes)
    if not yes:
        from vibe3.clients import GitClient
        from vibe3.models import BranchSource, UncommittedSource

        git = GitClient()
        branch_files = git.get_changed_files(
            BranchSource(branch=current_branch, base=resolved_base.base_branch)
        )
        uncommitted = git.get_changed_files(UncommittedSource())
        if not branch_files and not uncommitted:
            typer.echo(
                "No changes detected. Skipping review.\n"
                "Use --yes to force review anyway.",
                err=True,
            )
            raise typer.Exit(0)
        log.info(
            "Changes detected: {} committed + {} uncommitted",
            len(branch_files),
            len(uncommitted),
        )

    request, issue_number, _ = build_base_review_request(
        current_branch,
        resolved_base.base_branch,
        flow_service=flow_service,
    )

    result = publish_and_wait(
        ManualReviewIntent(
            issue_number=issue_number,
            branch=current_branch,
            is_base_review=True,
            request=request,
            instructions=instructions,
            dry_run=dry_run,
            no_async=no_async,
            show_prompt=show_prompt,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
        )
    )

    if result is None:
        typer.echo("Review dispatched (async mode)")
    else:
        # Sync mode: display result
        report_ref = _resolve_report_ref(current_branch)
        _emit_review_result(result, report_ref)
        if result.verdict in {"MAJOR", "BLOCK", "REFUSE", "UNKNOWN", "ERROR"}:
            raise typer.Exit(1)
