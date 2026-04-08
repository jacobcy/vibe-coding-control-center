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
    help="Create implementation plans using codeagent-wrapper",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


def _build_plan_usecase(config: VibeConfig, flow_service: FlowService) -> PlanUsecase:
    """Construct plan usecase with command-local dependencies."""
    return PlanUsecase(
        config=config,
        flow_service=flow_service,
    )


def _plan_issue_impl(
    issue: Annotated[
        int | None,
        typer.Argument(help="Issue number (default: current flow's task issue)"),
    ] = None,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Additional task guidance"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    async_mode: _ASYNC_OPT = True,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Create implementation plan for an issue."""
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()
    flow_service, branch = ensure_flow_for_current_branch()
    usecase = _build_plan_usecase(config, flow_service)

    # Resolve task input
    try:
        task_input = usecase.resolve_task_plan(branch, issue)
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if task_input.used_flow_issue:
        typer.echo(f"-> Using flow task: Issue #{task_input.issue_number}")

    typer.echo(f"-> Plan: Issue #{task_input.issue_number}")

    # Execute plan
    try:
        result = usecase.execute_plan(
            request=task_input.request,
            issue_number=task_input.issue_number,
            branch=branch,
            async_mode=async_mode,
        )

        if result.success:
            typer.echo("[green]✓[/] Plan created successfully")
        else:
            typer.echo(f"[red]✗[/] Plan failed: {result.stderr}", err=True)
            raise typer.Exit(1)
    except Exception as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error


def _plan_spec_impl(
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
    async_mode: _ASYNC_OPT = True,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Create implementation plan from a specification."""
    if trace:
        enable_trace()

    if file and msg:
        typer.echo("Error: Provide either --file or --msg, not both.", err=True)
        raise typer.Exit(1)

    if not file and not msg:
        typer.echo("Error: Provide either --file or --msg.", err=True)
        raise typer.Exit(1)

    config = VibeConfig.get_defaults()
    flow_service, branch = ensure_flow_for_current_branch()
    usecase = _build_plan_usecase(config, flow_service)

    # Resolve spec input
    try:
        spec_input = usecase.resolve_spec_plan(branch, file, msg)
    except FileNotFoundError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if file:
        typer.echo(f"-> Plan from file: {file}")
    elif msg:
        typer.echo(f"-> Plan: {msg[:60]}{'...' if len(msg) > 60 else ''}")

    # Bind spec if file provided
    if spec_input.spec_path and not dry_run:
        try:
            usecase.bind_spec(branch, spec_input.spec_path)
        except Exception:
            pass

    # Execute plan
    try:
        result = usecase.execute_plan(
            request=spec_input.request,
            issue_number=0,  # Spec mode doesn't use issue number
            branch=branch,
            async_mode=async_mode,
        )

        if result.success:
            typer.echo("[green]✓[/] Plan created successfully")
        else:
            typer.echo(f"[red]✗[/] Plan failed: {result.stderr}", err=True)
            raise typer.Exit(1)
    except Exception as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error


@app.callback()
def default(
    ctx: typer.Context,
    issue: Annotated[
        int | None,
        typer.Option(
            "--issue",
            help="Issue number (default: current flow's task issue)",
        ),
    ] = None,
    spec: Annotated[
        bool,
        typer.Option(
            "--spec",
            help="Create implementation plan from a specification",
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
    async_mode: _ASYNC_OPT = True,
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
            async_mode=async_mode,
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
            async_mode=async_mode,
            agent=agent,
            backend=backend,
            model=model,
        )
        return
    if file is not None or msg is not None:
        typer.echo("Error: --file/--msg require --spec.", err=True)
        raise typer.Exit(1)
    typer.echo(ctx.get_help())
    raise typer.Exit()


@app.command(name="issue", hidden=True)
@app.command(name="task", hidden=True)
def issue_command(
    issue: Annotated[
        int | None,
        typer.Argument(help="Issue number (default: current flow's task issue)"),
    ] = None,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Additional task guidance"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    async_mode: _ASYNC_OPT = True,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    _plan_issue_impl(
        issue=issue,
        instructions=instructions,
        trace=trace,
        dry_run=dry_run,
        async_mode=async_mode,
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
    async_mode: _ASYNC_OPT = True,
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
        async_mode=async_mode,
        agent=agent,
        backend=backend,
        model=model,
    )
