"""Run command - Execute implementation plans using codeagent-wrapper."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.commands.command_options import (
    _AGENT_OPT,
    _ASYNC_OPT,
    _BACKEND_OPT,
    _DRY_RUN_OPT,
    _MODEL_OPT,
    _TRACE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.commands.plan_helpers import get_agent_options
from vibe3.config.settings import VibeConfig
from vibe3.services.execution_pipeline import run_execution_pipeline
from vibe3.services.label_integration import transition_to_in_progress
from vibe3.services.run_context_builder import build_run_context
from vibe3.services.run_usecase import RunUsecase
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="run",
    help="Execute implementation plans using codeagent-wrapper",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


def _run_execution(
    plan_file: str | None,
    config: VibeConfig,
    dry_run: bool,
    instructions: str | None,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    usecase = RunUsecase(config=config)
    request = usecase.create_execution_request(
        plan_file=plan_file,
        instructions=instructions,
        agent=agent,
        backend=backend,
        model=model,
        context_builder=build_run_context,
        options_builder=get_agent_options,
        dry_run=dry_run,
    )
    run_execution_pipeline(request)


def _find_skill_file(skill_name: str) -> Path | None:
    """Find SKILL.md for a named skill under skills/ directory."""
    return RunUsecase.find_skill_file(skill_name)


def _run_skill(
    skill_name: str,
    instructions: str | None,
    config: VibeConfig,
    dry_run: bool,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    skill_file = _find_skill_file(skill_name)
    if not skill_file:
        typer.echo(
            f"Error: Skill '{skill_name}' not found (skills/{skill_name}/SKILL.md)",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"-> Skill: {skill_file}")
    skill_content = skill_file.read_text(encoding="utf-8")
    usecase = RunUsecase(config=config)
    request = usecase.create_skill_execution_request(
        skill_name=skill_name,
        skill_content=skill_content,
        instructions=instructions,
        agent=agent,
        backend=backend,
        model=model,
        options_builder=get_agent_options,
        dry_run=dry_run,
    )
    run_execution_pipeline(request)


def run_command(
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Instructions to pass to codeagent"),
    ] = None,
    plan: Annotated[
        Optional[Path],
        typer.Option(
            "--plan", "-p", help="Path to plan file (overrides flow plan_ref)"
        ),
    ] = None,
    skill: Annotated[
        Optional[str],
        typer.Option("--skill", "-s", help="Run a skill from skills/<name>/SKILL.md"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    async_mode: _ASYNC_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Execute implementation plan or skill using codeagent-wrapper.

    Default: runs current flow's plan_ref.
    Use --plan to specify a plan file, or --skill to run a project skill.
    Use --async to run in background.
    """
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()
    flow_service, branch = ensure_flow_for_current_branch()
    usecase = RunUsecase(config=config, flow_service=flow_service)

    if async_mode and not dry_run:
        from vibe3.services.async_execution_service import AsyncExecutionService

        async_svc = AsyncExecutionService()
        cmd = usecase.build_async_command(
            instructions, plan, skill, agent, backend, model
        )
        async_svc.start_async_execution("executor", cmd, branch)
        typer.echo("✓ Execution started in background")
        typer.echo("  vibe3 flow show    # Check status")
        return

    # --skill mode
    if skill:
        _run_skill(skill, instructions, config, dry_run, agent, backend, model)
        return

    try:
        summary = usecase.resolve_run_mode(branch, instructions, plan, skill)
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if summary.mode == "plan":
        plan_file = summary.plan_file
        log = logger.bind(domain="run", action="run", plan_file=plan_file)
        log.info("Starting plan execution")
        typer.echo(f"-> Execute: {plan_file}")
    elif summary.mode == "lightweight":
        plan_file = None
        log = logger.bind(domain="run", action="run", plan_file="(lightweight)")
        log.info("Starting lightweight execution")
        typer.echo("-> Lightweight mode: running with instructions only")
        if summary.message:
            typer.echo(summary.message)
    else:
        plan_file = summary.plan_file
        log = logger.bind(domain="run", action="run", plan_file=plan_file)
        log.info("Starting plan execution from flow")
        typer.echo(f"-> Using flow plan: {plan_file}")

    _run_execution(plan_file, config, dry_run, instructions, agent, backend, model)

    issue_number = usecase.transition_issue(branch)
    if not dry_run and issue_number:
        result = transition_to_in_progress(int(issue_number))
        if not result.success and result.error and result.error != "no_issue_bound":
            typer.echo(
                f"Warning: Failed to transition issue state: {result.error}",
                err=True,
            )


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    instructions: Annotated[
        Optional[str],
        typer.Argument(help="Instructions to pass to codeagent"),
    ] = None,
    plan: Annotated[
        Optional[Path],
        typer.Option(
            "--plan", "-p", help="Path to plan file (overrides flow plan_ref)"
        ),
    ] = None,
    skill: Annotated[
        Optional[str],
        typer.Option("--skill", "-s", help="Run a skill from skills/<name>/SKILL.md"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    async_mode: _ASYNC_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    run_command(
        instructions,
        plan,
        skill,
        trace,
        dry_run,
        async_mode,
        agent,
        backend,
        model,
    )
