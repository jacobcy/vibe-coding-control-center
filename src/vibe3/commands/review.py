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
    validate_model_backend_dependency,
    validate_show_prompt_dependency,
)
from vibe3.commands.common import enable_method_trace
from vibe3.commands.pr_helpers import build_base_resolution_usecase
from vibe3.config import load_runtime_config
from vibe3.config.cli_overrides import build_role_cli_overrides
from vibe3.exceptions import ConfigError, UserError
from vibe3.execution.issue_role_sync_runner import (
    run_issue_role_async,
    run_issue_role_sync,
)
from vibe3.roles.review import (
    REVIEW_SYNC_SPEC,
    build_base_review_request,
    execute_manual_review_async,
    execute_manual_review_sync,
    validate_review_prerequisites,
)
from vibe3.services import FlowService, resolve_branch_arg

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


def _emit_review_result(verdict: str, handoff_file: str | None) -> None:
    """Render review result summary consistently."""
    if verdict in {"ASYNC", "DRY_RUN"}:
        return
    typer.echo(f"\n=== Verdict: {verdict} ===")
    if handoff_file:
        typer.echo(f"-> Review saved to: {handoff_file}")


def _review_branch_impl(
    branch: str,
    trace: bool,
    dry_run: bool,
    no_async: bool,
    show_prompt: bool,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
) -> None:
    """Review implementation for a branch via role sync runner."""
    if trace:
        enable_method_trace()

    # Build cli_overrides and load config
    cli_overrides = build_role_cli_overrides("review", agent, backend, model)
    try:
        config = load_runtime_config(cli_overrides=cli_overrides or None)
    except ConfigError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1) from e

    # Validate --model requires backend (CLI or config)
    config_backend = config.review.agent_config.backend if config else None
    validate_model_backend_dependency(model, backend, config_backend)

    flow_service = FlowService()
    try:
        _, issue_number = validate_review_prerequisites(flow_service, branch)
    except UserError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    # Handle dry_run early return (align with plan command pattern)
    # dry_run early-return: bypasses async/sync execution
    # to display command/prompt for verification
    if dry_run:
        run_issue_role_sync(
            issue_number=issue_number,
            dry_run=True,
            fresh_session=fresh_session,
            show_prompt=show_prompt,
            spec=REVIEW_SYNC_SPEC,
            agent=agent,
            backend=backend,
            model=model,
        )
        return

    if no_async:
        run_issue_role_sync(
            issue_number=issue_number,
            dry_run=False,
            fresh_session=fresh_session,
            show_prompt=show_prompt,
            spec=REVIEW_SYNC_SPEC,
            agent=agent,
            backend=backend,
            model=model,
        )
    else:
        run_issue_role_async(
            issue_number=issue_number,
            dry_run=False,
            spec=REVIEW_SYNC_SPEC,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
        )


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    branch: BranchOption = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
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

    # Build cli_overrides and load config
    cli_overrides = build_role_cli_overrides("review", agent, backend, model)
    try:
        config = load_runtime_config(cli_overrides=cli_overrides or None)
    except ConfigError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1) from e

    # Validate --model requires backend (CLI or config)
    config_backend = config.review.agent_config.backend if config else None
    validate_model_backend_dependency(model, backend, config_backend)

    flow_service, current_branch = ensure_flow_for_current_branch()
    try:
        resolved_base = build_base_resolution_usecase().resolve_review_base(
            base_branch,
            current_branch=current_branch,
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

    request, issue_number, _ = build_base_review_request(
        current_branch,
        resolved_base.base_branch,
        flow_service=flow_service,
    )
    if no_async or dry_run:
        result = execute_manual_review_sync(
            request=request,
            dry_run=dry_run,
            instructions=instructions,
            issue_number=issue_number,
            branch=current_branch,
            show_prompt=show_prompt,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
        )
    else:
        result = execute_manual_review_async(
            request=request,
            instructions=instructions,
            issue_number=issue_number,
            branch=current_branch,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
        )
        if result.tmux_session:
            typer.echo(f"tmux session: {result.tmux_session}")
        if result.log_path:
            typer.echo(f"log: {result.log_path}")
    _emit_review_result(result.verdict, result.handoff_file)
    if result.verdict in {"MAJOR", "BLOCK", "REFUSE", "UNKNOWN", "ERROR"}:
        raise typer.Exit(1)
