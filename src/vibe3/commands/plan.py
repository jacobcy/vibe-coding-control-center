"""Plan command."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from vibe3.commands.command_options import (
    _ASYNC_OPT,
    _DRY_RUN_OPT,
    _SHOW_PROMPT_OPT,
    _TRACE_OPT,
)
from vibe3.execution.issue_role_sync_runner import (
    run_issue_role_async,
    run_issue_role_sync,
)
from vibe3.roles.plan import (
    PLAN_SYNC_SPEC,
    execute_spec_plan_async,
    execute_spec_plan_sync,
    resolve_spec_plan_input,
)
from vibe3.services.flow_service import FlowService
from vibe3.utils.branch_arg import resolve_branch_arg
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="plan",
    help="Create implementation plans for issues or specifications.",
    no_args_is_help=True,
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
) -> None:
    """Create implementation plan for a branch with spec_ref."""
    if trace:
        enable_trace()

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
            f"Error: No issue linked to flow '{branch}'.\n"
            "Run 'vibe flow bind <issue>' first.",
            err=True,
        )
        raise typer.Exit(1)

    if no_async:
        run_issue_role_sync(
            issue_number=issue_number,
            dry_run=dry_run,
            fresh_session=False,
            show_prompt=show_prompt,
            spec=PLAN_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue_number,
            dry_run=dry_run,
            spec=PLAN_SYNC_SPEC,
        )


def _plan_spec_impl(
    branch: str,
    spec_path: Path | None,
    trace: bool,
    dry_run: bool,
    no_async: bool,
) -> None:
    """Create implementation plan from a specification file."""
    if trace:
        enable_trace()

    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)

    if not flow:
        typer.echo(
            f"Error: No flow for branch '{branch}'.\n"
            "Run 'vibe3 flow update' or 'vibe3 flow bind <issue> --role task' first.",
            err=True,
        )
        raise typer.Exit(1)

    # If spec_path provided, update flow's spec_ref
    if spec_path:
        if not spec_path.exists() or not spec_path.is_file():
            typer.echo(f"Error: Spec file not found: {spec_path}", err=True)
            raise typer.Exit(1)
        resolved_spec = str(spec_path.resolve())
        flow_service.bind_spec(branch, resolved_spec, actor=None)
        typer.echo(f"Spec updated: {resolved_spec}")
        spec_file = spec_path
    else:
        # Use existing spec_ref from flow
        if not flow.spec_ref:
            typer.echo(
                "Error: No spec bound.\n"
                "Use 'vibe3 plan --spec <file>' to bind a spec, or "
                "'vibe3 flow bind <issue> --role task' first.",
                err=True,
            )
            raise typer.Exit(1)
        spec_file = Path(flow.spec_ref)
        typer.echo(f"Using flow spec: {flow.spec_ref}")

    if dry_run:
        typer.echo("Plan dry run for specification")
        return

    issue_number = flow.task_issue_number

    if not issue_number:
        typer.echo(
            "Warning: No issue linked to flow. Lifecycle events will be skipped.",
            err=True,
        )

    # Build request from spec file
    try:
        spec_input = resolve_spec_plan_input(branch, file=spec_file)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    if no_async:
        execute_spec_plan_sync(
            request=spec_input.request,
            issue_number=issue_number,
            branch=branch,
        )
    else:
        spec_arg = str(spec_path) if spec_path else None
        execute_spec_plan_async(
            request=spec_input.request,
            issue_number=issue_number,
            branch=branch,
            cli_args=[
                "plan",
                *(["--spec", spec_arg] if spec_arg else []),
            ],
        )


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    branch: BranchOption = None,
    spec: Annotated[
        Optional[Path],
        typer.Option(
            "--spec",
            help="Spec file path (replaces flow spec_ref; omit to use flow spec_ref)",
        ),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    target_branch = resolve_branch_arg(branch)

    if spec is not None:
        _plan_spec_impl(
            branch=target_branch,
            spec_path=spec,
            trace=trace,
            dry_run=dry_run,
            no_async=no_async,
        )
        return

    # Default: plan for branch
    _plan_for_branch(
        branch=target_branch,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
    )


@app.command(name="issue", hidden=True)
def issue_command(
    issue: Annotated[int, typer.Argument(help="GitHub issue number")],
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Additional task guidance"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
) -> None:
    """Legacy: plan from issue number (use --branch instead)."""
    _ = instructions
    from vibe3.services.issue_flow_service import IssueFlowService

    branch = IssueFlowService().canonical_branch_name(issue)
    _plan_for_branch(
        branch=branch,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
    )
