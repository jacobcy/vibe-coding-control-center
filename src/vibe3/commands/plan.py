"""Plan command."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from vibe3.agents.plan_agent import PlanUsecase
from vibe3.agents.plan_prompt import (
    make_plan_context_builder,
)
from vibe3.agents.runner import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.commands.command_options import (
    _AGENT_OPT,
    _ASYNC_OPT,
    _BACKEND_OPT,
    _DRY_RUN_OPT,
    _MODEL_OPT,
    _TRACE_OPT,
    _WORKTREE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.config.settings import VibeConfig
from vibe3.models.plan import PlanRequest
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    confirm_plan_handoff as _svc_confirm_handoff,
)
from vibe3.services.issue_failure_service import (
    fail_planner_issue as _svc_fail_planner,
)
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


def _execute_plan_command(
    *,
    config: VibeConfig,
    branch: str,
    request: PlanRequest,
    instructions: str | None,
    dry_run: bool,
    async_mode: bool,
    agent: str | None,
    backend: str | None,
    model: str | None,
    worktree: bool,
) -> object:
    plan_prompt = config.plan.plan_prompt if getattr(config, "plan", None) else None
    command = create_codeagent_command(
        role="planner",
        context_builder=make_plan_context_builder(request, config),
        task=instructions or plan_prompt,
        dry_run=dry_run,
        handoff_kind="plan",
        agent=agent,
        backend=backend,
        model=model,
        worktree=worktree,
        config=config,
        branch=branch,
    )
    return CodeagentExecutionService(config).execute(command, async_mode=async_mode)


def _comment_and_fail_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str,
) -> None:
    """Record planner failure and move the issue into failed."""
    _svc_fail_planner(
        issue_number=issue_number,
        reason=reason,
        actor=actor,
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
    worktree: _WORKTREE_OPT = False,
) -> None:
    """Create implementation plan for an issue."""
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()
    flow_service, branch = ensure_flow_for_current_branch()
    usecase = _build_plan_usecase(config, flow_service)

    try:
        task_input = usecase.resolve_task_plan(branch, issue)
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    if task_input.used_flow_issue:
        typer.echo(f"-> Using flow task: Issue #{task_input.issue_number}")

    typer.echo(f"-> Plan: Issue #{task_input.issue_number}")
    try:
        result = _execute_plan_command(
            config=config,
            branch=branch,
            request=task_input.request,
            instructions=instructions,
            dry_run=dry_run,
            async_mode=async_mode,
            agent=agent,
            backend=backend,
            model=model,
            worktree=worktree,
        )
    except BaseException as error:
        if dry_run or async_mode:
            raise
        _comment_and_fail_issue(
            issue_number=task_input.issue_number,
            reason=str(error) or "planner execution raised an unexpected error",
            actor="agent:plan",
        )
        typer.echo(
            "Error: Planner execution failed; issue moved to state/failed",
            err=True,
        )
        raise typer.Exit(1) from error

    if not dry_run and not async_mode:
        if getattr(result, "success", False):
            transition = _svc_confirm_handoff(
                issue_number=task_input.issue_number,
                actor="agent:plan",
            )
            if transition == "blocked":
                typer.echo(
                    "Warning: Failed to transition issue state: "
                    "state_transition_blocked",
                    err=True,
                )
        else:
            _comment_and_fail_issue(
                issue_number=task_input.issue_number,
                reason=getattr(result, "stderr", "") or "planner exited with failure",
                actor="agent:plan",
            )
            typer.echo(
                "Error: Planner execution failed; issue moved to state/failed",
                err=True,
            )
            raise typer.Exit(1)


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
    worktree: _WORKTREE_OPT = False,
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

    if spec_input.spec_path and not dry_run:
        try:
            usecase.bind_spec(branch, spec_input.spec_path)
        except Exception:
            pass

    result = _execute_plan_command(
        config=config,
        branch=branch,
        request=spec_input.request,
        instructions=instructions,
        dry_run=dry_run,
        async_mode=async_mode,
        agent=agent,
        backend=backend,
        model=model,
        worktree=worktree,
    )

    if not dry_run and not async_mode and not getattr(result, "success", False):
        typer.echo("Error: Planner execution failed for spec mode", err=True)
        raise typer.Exit(1)


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
    worktree: _WORKTREE_OPT = False,
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
            worktree=worktree,
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
            worktree=worktree,
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
    worktree: _WORKTREE_OPT = False,
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
        worktree=worktree,
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
    worktree: _WORKTREE_OPT = False,
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
        worktree=worktree,
    )
