"""Run command."""

from pathlib import Path
from typing import Annotated, Callable, Optional

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
from vibe3.config.settings import VibeConfig
from vibe3.services.codeagent_execution_service import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.services.label_integration import transition_to_in_progress
from vibe3.services.run_context_builder import build_run_context
from vibe3.services.run_usecase import RunUsecase
from vibe3.utils.trace import enable_trace

app = typer.Typer(name="run", help="Execute implementation plans using codeagent-wrapper", no_args_is_help=False, invoke_without_command=True, rich_markup_mode="rich")


def _find_skill_file(skill_name: str) -> Path | None:
    return RunUsecase.find_skill_file(skill_name)

def _execute_run_command(
    *,
    config: VibeConfig,
    branch: str,
    instructions: str | None,
    context_builder: Callable[[], str],
    dry_run: bool,
    async_mode: bool,
    agent: str | None,
    backend: str | None,
    model: str | None,
    handoff_metadata: dict[str, object] | None,
) -> None:
    run_prompt = config.run.run_prompt if getattr(config, "run", None) else None
    command = create_codeagent_command(
        role="executor",
        context_builder=context_builder,
        task=instructions or run_prompt,
        dry_run=dry_run,
        handoff_kind="run",
        handoff_metadata=handoff_metadata,
        agent=agent,
        backend=backend,
        model=model,
        config=config,
        branch=branch,
    )
    CodeagentExecutionService(config).execute(command, async_mode=async_mode)


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
    """Execute implementation plan or skill."""
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()
    flow_service, branch = ensure_flow_for_current_branch()
    usecase = RunUsecase(flow_service=flow_service)

    if skill:
        skill_file = _find_skill_file(skill)
        if not skill_file:
            typer.echo(
                f"Error: Skill '{skill}' not found (skills/{skill}/SKILL.md)",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"-> Skill: {skill_file}")
        skill_content = skill_file.read_text(encoding="utf-8")
        _execute_run_command(
            config=config,
            branch=branch,
            instructions=instructions or f"Execute skill: {skill}",
            context_builder=lambda: skill_content,
            dry_run=dry_run,
            async_mode=async_mode,
            agent=agent,
            backend=backend,
            model=model,
            handoff_metadata={"skill": skill},
        )
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

    _execute_run_command(
        config=config,
        branch=branch,
        instructions=instructions,
        context_builder=lambda: build_run_context(plan_file, config),
        dry_run=dry_run,
        async_mode=async_mode,
        agent=agent,
        backend=backend,
        model=model,
        handoff_metadata={"plan_ref": plan_file} if plan_file else None,
    )

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
