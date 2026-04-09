"""Plan command."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from vibe3.agents.plan_agent import PlanUsecase
from vibe3.commands.command_options import (
    _AGENT_OPT,
    _ASYNC_OPT,
    _BACKEND_OPT,
    _DRY_RUN_OPT,
    _MODEL_OPT,
    _TRACE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.config.settings import VibeConfig
from vibe3.services.flow_service import FlowService
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="plan",
    help="Create implementation plans for issues or specifications.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _build_plan_usecase(
    flow_service: FlowService | None = None,
) -> PlanUsecase:
    """Construct plan usecase with command-local dependencies."""
    return PlanUsecase(
        flow_service=flow_service,
        config=VibeConfig.get_defaults(),
    )


def _plan_issue_impl(
    issue: int,
    instructions: str | None,
    trace: bool,
    dry_run: bool,
    no_async: bool,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    """Create implementation plan for an issue."""
    if trace:
        enable_trace()

    flow_service, branch = ensure_flow_for_current_branch()
    usecase = _build_plan_usecase(flow_service=flow_service)

    # 1. Resolve task input
    task_input = usecase.resolve_task_plan(branch, issue_number=issue)

    # 2. Execute
    if dry_run:
        typer.echo(f"Plan dry run for issue #{task_input.issue_number}")
        return

    usecase.execute_plan(
        request=task_input.request,
        issue_number=task_input.issue_number,
        branch=task_input.branch,
        async_mode=not no_async,
        cli_args=[
            "plan",
            "issue",
            str(task_input.issue_number),
            *([instructions] if instructions else []),
        ],
    )


def _plan_spec_impl(
    file: Path | None,
    msg: str | None,
    instructions: str | None,
    trace: bool,
    dry_run: bool,
    no_async: bool,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    """Create implementation plan from a specification."""
    if trace:
        enable_trace()

    flow_service, branch = ensure_flow_for_current_branch()
    usecase = _build_plan_usecase(flow_service=flow_service)

    # 1. Resolve spec input
    try:
        spec_input = usecase.resolve_spec_plan(branch, file=file, msg=msg)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # 2. Bind spec if not dry-run
    if not dry_run and spec_input.spec_path:
        usecase.bind_spec(branch, spec_input.spec_path)

    # 3. Execute
    if dry_run:
        typer.echo("Plan dry run for specification")
        return

    flow = flow_service.get_flow_status(branch)
    issue_number = flow.task_issue_number if flow else None

    if not issue_number:
        typer.echo(
            "Warning: No issue linked to flow. Lifecycle events will be skipped.",
            err=True,
        )

    usecase.execute_plan(
        request=spec_input.request,
        issue_number=issue_number,
        branch=branch,
        async_mode=not no_async,
        cli_args=[
            "plan",
            "spec",
            *(["--file", str(file)] if file else []),
            *(["--msg", msg] if msg else []),
            *([instructions] if instructions else []),
        ],
    )


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    issue: Annotated[
        Optional[int],
        typer.Option("--issue", "-i", help="GitHub issue number"),
    ] = None,
    spec: Annotated[
        bool,
        typer.Option(
            "--spec", help="Plan from specification (requires --file or --msg)"
        ),
    ] = False,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Path to spec file"),
    ] = None,
    msg: Annotated[
        Optional[str],
        typer.Option("--msg", help="Spec description"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if issue is not None and spec:
        typer.echo("Error: --issue and --spec are mutually exclusive.", err=True)
        raise typer.Exit(1)
    if issue is not None:
        _plan_issue_impl(
            issue=issue,
            instructions=None,
            trace=trace,
            dry_run=dry_run,
            no_async=no_async,
            agent=agent,
            backend=backend,
            model=model,
        )
        return
    if spec:
        _plan_spec_impl(
            file=file,
            msg=msg,
            instructions=None,
            trace=trace,
            dry_run=dry_run,
            no_async=no_async,
            agent=agent,
            backend=backend,
            model=model,
        )
        return
    if file is not None or msg is not None:
        typer.echo("Error: --file/--msg require --spec.", err=True)
        raise typer.Exit(1)

    # If no issue or spec, show help
    typer.echo(ctx.get_help())


@app.command(name="issue")
def issue_command(
    issue: Annotated[int, typer.Argument(help="GitHub issue number")],
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Additional task guidance"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    _plan_issue_impl(
        issue=issue,
        instructions=instructions,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        agent=agent,
        backend=backend,
        model=model,
    )


@app.command(hidden=True)
def spec(
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Path to spec file"),
    ] = None,
    msg: Annotated[
        Optional[str],
        typer.Option("--msg", help="Spec description"),
    ] = None,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Additional task guidance"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    no_async: _ASYNC_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    _plan_spec_impl(
        file=file,
        msg=msg,
        instructions=instructions,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        agent=agent,
        backend=backend,
        model=model,
    )
