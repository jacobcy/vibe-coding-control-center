"""Run command."""

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
    _SHOW_PROMPT_OPT,
    _TRACE_OPT,
)
from vibe3.config.settings import VibeConfig
from vibe3.roles.run import (
    ensure_plan_file_exists,
    execute_manual_run,
    find_skill_file,
    resolve_run_mode,
)
from vibe3.services.flow_service import FlowService
from vibe3.utils.branch_arg import resolve_branch_arg
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="run",
    help="Execute implementation plans using codeagent-wrapper",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)

BranchOption = Annotated[
    str | None,
    typer.Option("--branch", "-b", help="Branch name or issue number (e.g., 320)"),
]


def run_command(
    branch: BranchOption = None,
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
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
    fresh_session: Annotated[
        bool,
        typer.Option(
            "--fresh-session",
            help="Skip session resume and start a fresh agent session",
        ),
    ] = False,
    publish: Annotated[
        bool,
        typer.Option("--publish", help="Publish mode: create commit + PR"),
    ] = False,
) -> None:
    """Execute implementation plan or skill."""
    if trace:
        enable_trace()

    # Register EDA event handlers for run command (may publish events)
    from vibe3.domain.handlers import register_event_handlers

    register_event_handlers()

    config = VibeConfig.get_defaults()
    target_branch = resolve_branch_arg(branch)

    flow_service = FlowService()
    flow = flow_service.get_flow_status(target_branch)

    if not flow:
        typer.echo(f"Error: No flow for branch '{target_branch}'.", err=True)
        raise typer.Exit(1)

    issue_number = (
        str(flow.task_issue_number) if flow and flow.task_issue_number else None
    )

    if publish and skill:
        typer.echo("Error: --publish and --skill are mutually exclusive.", err=True)
        raise typer.Exit(1)

    if publish:
        skill = "vibe-commit"
        typer.echo("-> Publish mode: creating commit + PR")

    if skill:
        skill_file = find_skill_file(skill)
        if not skill_file:
            typer.echo(
                f"Error: Skill '{skill}' not found (skills/{skill}/SKILL.md)",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"-> Skill: {skill_file}")
        execute_manual_run(
            config=config,
            branch=target_branch,
            issue_number=int(issue_number) if issue_number else None,
            instructions=instructions,
            plan_file=None,
            skill=skill,
            summary=resolve_run_mode(
                flow_service, target_branch, instructions, None, skill
            ),
            dry_run=dry_run,
            no_async=no_async,
            show_prompt=show_prompt,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
        )
        return

    try:
        summary = resolve_run_mode(
            flow_service, target_branch, instructions, plan, skill
        )
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

    try:
        ensure_plan_file_exists(plan_file)
    except FileNotFoundError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    execute_manual_run(
        config=config,
        branch=target_branch,
        issue_number=int(issue_number) if issue_number else None,
        instructions=instructions,
        plan_file=plan_file,
        skill=None,
        summary=summary,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
        agent=agent,
        backend=backend,
        model=model,
        fresh_session=fresh_session,
    )


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    branch: BranchOption = None,
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
    no_async: _ASYNC_OPT = False,
    show_prompt: _SHOW_PROMPT_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
    fresh_session: Annotated[
        bool,
        typer.Option(
            "--fresh-session",
            help="Skip session resume and start a fresh agent session",
        ),
    ] = False,
    publish: Annotated[
        bool,
        typer.Option("--publish", help="Publish mode: create commit + PR"),
    ] = False,
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    run_command(
        branch=branch,
        instructions=instructions,
        plan=plan,
        skill=skill,
        trace=trace,
        dry_run=dry_run,
        no_async=no_async,
        show_prompt=show_prompt,
        agent=agent,
        backend=backend,
        model=model,
        fresh_session=fresh_session,
        publish=publish,
    )
