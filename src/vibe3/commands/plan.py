"""Plan command."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from vibe3.agents.plan_agent import PlanUsecase
from vibe3.agents.runner import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.clients.github_client import GitHubClient
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
from vibe3.models.orchestration import IssueState
from vibe3.models.plan import PlanRequest
from vibe3.services.flow_service import FlowService
from vibe3.services.label_service import LabelService
from vibe3.services.plan_context_builder import (
    make_plan_context_builder,
)
from vibe3.services.spec_ref_service import SpecRefService
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="plan",
    help="Create implementation plans using codeagent-wrapper",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _build_plan_usecase(config: VibeConfig, flow_service: FlowService) -> PlanUsecase:
    """Construct plan usecase with command-local dependencies."""
    return PlanUsecase(
        config=config,
        flow_service=flow_service,
        github_client=GitHubClient(),
        spec_ref_service=SpecRefService(),
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
) -> None:
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
    CodeagentExecutionService(config).execute(command, async_mode=async_mode)


@app.command()
def task(
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
    async_mode: _ASYNC_OPT = False,
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
    _execute_plan_command(
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

    if not dry_run:
        result = LabelService().confirm_issue_state(
            task_input.issue_number,
            IssueState.CLAIMED,
            actor="agent:plan",
        )
        if result == "blocked":
            typer.echo(
                "Warning: Failed to transition issue state: state_transition_blocked",
                err=True,
            )


@app.command()
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
    async_mode: _ASYNC_OPT = False,
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

    _execute_plan_command(
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
