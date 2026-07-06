"""Plan command."""

from pathlib import Path
from typing import Annotated

import typer

from vibe3.commands.command_options import (
    _AGENT_OPT,
    _ASYNC_OPT,
    _BACKEND_OPT,
    _DRY_RUN_OPT,
    _FRESH_SESSION_OPT,
    _MODEL_OPT,
    _SHOW_PROMPT_OPT,
    _TRACE_OPT,
    load_config_and_validate_model,
    validate_show_prompt_dependency,
)
from vibe3.commands.common import _handle_codeagent_result, enable_method_trace
from vibe3.roles import (
    resolve_spec_plan_input,
)
from vibe3.services.flow import FlowService, resolve_branch_arg
from vibe3.services.handoff import resolve_handoff_target

app = typer.Typer(
    name="plan",
    help="Create implementation plans for issues or specifications.",
    no_args_is_help=False,
    rich_markup_mode="rich",
)

BranchOption = Annotated[
    str | None,
    typer.Option("--branch", "-b", help="Branch name or issue number (e.g., 320)"),
]


def _plan_for_branch(
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
    """Create implementation plan for a branch with spec_ref."""
    if trace:
        enable_method_trace()

    # Register EDA event handlers for plan command
    from vibe3.domain import register_event_handlers
    from vibe3.models import ManualPlanIntent, publish_and_wait

    register_event_handlers()

    # Load config and validate --model requires backend (CLI or config)
    _config = load_config_and_validate_model("plan", agent, backend, model)

    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)

    if not flow:
        typer.echo(
            f"Error: No flow for branch '{branch}'.\n"
            "Run 'vibe3 flow update' or 'vibe3 flow bind <issue> --role task' first.",
            err=True,
        )
        raise typer.Exit(1)

    if not flow.spec_ref:
        typer.echo(
            "Error: No spec bound.\n"
            "Run 'vibe flow bind <issue>' or 'vibe flow update --spec <file>'.",
            err=True,
        )
        raise typer.Exit(1)

    issue_number = flow.task_issue_number
    if not issue_number:
        typer.echo(
            "Warning: No issue linked to flow. Lifecycle events will be skipped.",
            err=True,
        )

    # Build request from spec file
    try:
        spec_input = resolve_spec_plan_input(branch)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Publish ManualPlanIntent event and wait for result
    result = publish_and_wait(
        ManualPlanIntent(
            issue_number=issue_number,
            branch=branch,
            request=spec_input.request,
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
    _handle_codeagent_result(result, "Plan")


def _plan_spec_impl(
    branch: str,
    spec_path: str | None,
    trace: bool,
    dry_run: bool,
    no_async: bool,
    show_prompt: bool,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
) -> None:
    """Create implementation plan from a specification file."""
    if trace:
        enable_method_trace()

    # Register EDA event handlers for plan command
    from vibe3.domain import register_event_handlers
    from vibe3.models import ManualPlanIntent, publish_and_wait

    register_event_handlers()

    # Load config and validate --model requires backend (CLI or config)
    _config = load_config_and_validate_model("plan", agent, backend, model)

    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)

    if not flow:
        typer.echo(
            f"Error: No flow for branch '{branch}'.\n"
            "Run 'vibe3 flow update' or 'vibe3 flow bind <issue> --role task' first.",
            err=True,
        )
        raise typer.Exit(1)

    spec_file: Path | None = None
    # When spec_ref is an issue number, we don't need a file path
    spec_is_issue = False

    # Resolve spec parameter: support both paths and issue numbers
    if spec_path is not None:
        if spec_path.startswith("@"):
            # @-prefixed: delegate to resolve_handoff_target (@spec, etc.)
            try:
                resolved = resolve_handoff_target(spec_path, branch=branch)
            except (FileNotFoundError, ValueError) as e:
                # If resolution fails, check if spec_ref is an issue number
                if flow.spec_ref and flow.spec_ref.lstrip("#").isdigit():
                    spec_is_issue = True
                    typer.echo(f"Using flow spec: {flow.spec_ref} (issue)")
                else:
                    typer.echo(f"Error: {e}", err=True)
                    raise typer.Exit(1)
            else:
                # Check if resolved value is an issue number
                if str(resolved).lstrip("#").isdigit():
                    spec_is_issue = True
                    typer.echo(f"Using flow spec: {flow.spec_ref} (issue)")
                else:
                    spec_file = Path(resolved)
                    typer.echo(f"Using flow spec: {flow.spec_ref}")
        else:
            # Direct value: check if it's an issue number or a file path
            if spec_path.lstrip("#").isdigit():
                # GP-1 (spec 012): --spec is a read-only per-run input override.
                # Issue numbers feed this plan run only; they MUST NOT be written
                # into spec_ref (G2 — issue identity belongs in task_issue_number).
                # Bind a spec via `vibe3 flow update --spec` or `vibe3 handoff spec`.
                spec_is_issue = True
                typer.echo(f"Using spec (read-only): #{spec_path.lstrip('#')} (issue)")
            else:
                resolved_spec = Path(spec_path)
                if not resolved_spec.exists() or not resolved_spec.is_file():
                    typer.echo(f"Error: Spec file not found: {spec_path}", err=True)
                    raise typer.Exit(1)
                # GP-1 (spec 012): --spec is a read-only per-run input override.
                # Bind a spec via `vibe3 flow update --spec` or `vibe3 handoff spec`
                # (canonical writer, FR-001/002).
                typer.echo(f"Using spec (read-only): {resolved_spec}")
                spec_file = resolved_spec
    else:
        # No --spec parameter: default to flow's spec_ref
        if not flow.spec_ref:
            typer.echo(
                "Error: No spec bound.\n"
                "Use 'vibe3 plan --spec <file>' to bind a spec, or "
                "'vibe3 flow bind <issue> --role task' first.",
                err=True,
            )
            raise typer.Exit(1)
        # Check if spec_ref is an issue number
        if flow.spec_ref.lstrip("#").isdigit():
            spec_is_issue = True
            typer.echo(f"Using flow spec: {flow.spec_ref} (issue)")
        else:
            spec_file = Path(flow.spec_ref)
            typer.echo(f"Using flow spec: {flow.spec_ref}")

    issue_number = flow.task_issue_number

    if not issue_number:
        typer.echo(
            "Warning: No issue linked to flow. Lifecycle events will be skipped.",
            err=True,
        )

    # Build request from spec file or issue
    try:
        # When spec is an issue number, pass None to use SpecRefService logic
        spec_input = resolve_spec_plan_input(
            branch, file=None if spec_is_issue else spec_file
        )
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Publish ManualPlanIntent event and wait for result
    result = publish_and_wait(
        ManualPlanIntent(
            issue_number=issue_number,
            branch=branch,
            request=spec_input.request,
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
    _handle_codeagent_result(result, "Plan")


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    branch: BranchOption = None,
    spec: Annotated[
        str | None,
        typer.Option(
            "--spec",
            help="Spec reference: file path, issue number, or '@spec' alias",
        ),
    ] = None,
    task: Annotated[
        str | None,
        typer.Option(
            "--task",
            help="[DEPRECATED] Alias for --spec (hidden)",
            hidden=True,
        ),
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
    if ctx.invoked_subcommand is not None:
        return

    target_branch = resolve_branch_arg(branch)

    # Validate --show-prompt requires --dry-run
    validate_show_prompt_dependency(dry_run, show_prompt)

    # --task is alias for --spec (backward compatibility)
    spec_path = spec or task

    if spec_path is not None:
        _plan_spec_impl(
            branch=target_branch,
            spec_path=spec_path,
            trace=trace,
            dry_run=dry_run,
            no_async=no_async,
            show_prompt=show_prompt,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
        )
        return

    # Default: plan for branch
    _plan_for_branch(
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
    """Legacy alias: plan --branch <issue>."""
    default(
        ctx=ctx,
        branch=str(issue),
        spec=None,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
        agent=agent,
        backend=backend,
        model=model,
        fresh_session=fresh_session,
    )
