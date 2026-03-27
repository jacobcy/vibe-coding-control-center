"""Plan command - Create implementation plans using codeagent-wrapper."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from vibe3.clients.github_client import GitHubClient
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
from vibe3.services.codeagent_execution_service import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.services.flow_service import FlowService
from vibe3.services.label_integration import transition_to_claimed
from vibe3.services.plan_context_builder import build_plan_context
from vibe3.services.plan_usecase import PlanUsecase
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
) -> None:
    """Create implementation plan for an issue.

    If no issue number is provided, uses the current flow's task issue.

    Examples:
        vibe3 plan task              # Use current flow's task issue
        vibe3 plan task 42           # Plan for issue #42
        vibe3 plan task 42 --dry-run
        vibe3 plan task 42 "Focus on security"
        vibe3 plan task 42 --agent planner-pro
        vibe3 plan task 42 --async   # Run in background
    """
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
    plan_prompt = config.plan.plan_prompt if getattr(config, "plan", None) else None
    task = instructions or plan_prompt
    command = create_codeagent_command(
        role="planner",
        context_builder=lambda: build_plan_context(task_input.request, config),
        task=task,
        dry_run=dry_run,
        handoff_kind="plan",
        agent=agent,
        backend=backend,
        model=model,
        config=config,
        branch=branch,
    )
    CodeagentExecutionService(config).execute(command, async_mode=async_mode)

    if not dry_run:
        result = transition_to_claimed(task_input.issue_number)
        if not result.success and result.error and result.error != "no_issue_bound":
            typer.echo(
                f"Warning: Failed to transition issue state: {result.error}",
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
) -> None:
    """Create implementation plan from a specification.

    Provide either --file or --msg (not both).

    Examples:
        vibe3 plan spec --file spec.md
        vibe3 plan spec --msg "Add dark mode support"
        vibe3 plan spec -f spec.md "Prioritize performance"
        vibe3 plan spec --msg "Refactor auth" --agent planner-pro
        vibe3 plan spec --file spec.md --async  # Run in background
    """
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

    plan_prompt = config.plan.plan_prompt if getattr(config, "plan", None) else None
    task = instructions or plan_prompt
    command = create_codeagent_command(
        role="planner",
        context_builder=lambda: build_plan_context(spec_input.request, config),
        task=task,
        dry_run=dry_run,
        handoff_kind="plan",
        agent=agent,
        backend=backend,
        model=model,
        config=config,
        branch=branch,
    )
    CodeagentExecutionService(config).execute(command, async_mode=async_mode)
