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
    _FRESH_SESSION_OPT,
    _MODEL_OPT,
    _SHOW_PROMPT_OPT,
    _TRACE_OPT,
    validate_show_prompt_dependency,
)
from vibe3.commands.common import enable_method_trace
from vibe3.config import load_runtime_config
from vibe3.config.cli_overrides import build_role_cli_overrides
from vibe3.exceptions import ConfigError, UserError
from vibe3.roles import resolve_skill_path
from vibe3.roles.run import (
    ensure_plan_file_exists,
    execute_manual_run,
    resolve_run_mode,
    validate_run_prerequisites,
)
from vibe3.services import FlowService, resolve_branch_arg, resolve_handoff_target

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
        Optional[str],
        typer.Option(
            "--plan",
            "-p",
            help="Plan reference: file path or '@plan' to use flow's plan_ref",
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
    fresh_session: _FRESH_SESSION_OPT = False,
    publish: Annotated[
        bool,
        typer.Option("--publish", help="Publish mode: create commit + PR"),
    ] = False,
) -> None:
    """Execute implementation plan or skill."""
    if trace:
        enable_method_trace()

    # Validate --show-prompt requires --dry-run
    validate_show_prompt_dependency(dry_run, show_prompt)

    # Register EDA event handlers for run command (may publish events)
    from vibe3.domain.handlers import register_event_handlers

    register_event_handlers()

    cli_overrides = build_role_cli_overrides("run", agent, backend, model)

    try:
        config = load_runtime_config(
            cli_overrides=cli_overrides if cli_overrides else None
        )
    except ConfigError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1) from e

    target_branch = resolve_branch_arg(branch)

    flow_service = FlowService()
    try:
        flow, issue_number = validate_run_prerequisites(flow_service, target_branch)
    except UserError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if publish and skill:
        typer.echo("Error: --publish and --skill are mutually exclusive.", err=True)
        raise typer.Exit(1)

    if publish:
        skill = "vibe-commit"
        typer.echo("-> Publish mode: creating commit + PR")

    if skill:
        skill_path = resolve_skill_path(skill)
        if not skill_path:
            typer.echo(
                f"Error: Skill '{skill}' not found "
                "(no adapter provides it in current profile)",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"-> Skill: {skill_path}")
        execute_manual_run(
            config=config,
            branch=target_branch,
            issue_number=issue_number,
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
            publish=publish,
        )
        return

    # Resolve plan parameter using shared @-resolution channel
    resolved_plan: Path | None = None
    if plan is not None:
        if plan.startswith("@"):
            # @-prefixed: delegate to resolve_handoff_target (@plan, etc.)
            try:
                resolved_plan = resolve_handoff_target(plan, branch=target_branch)
                typer.echo(f"Using flow plan: {plan}")
            except (FileNotFoundError, ValueError) as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)
        else:
            # File path provided: override flow's plan_ref
            resolved_plan = Path(plan)
            if not resolved_plan.exists() or not resolved_plan.is_file():
                typer.echo(f"Error: Plan file not found: {plan}", err=True)
                raise typer.Exit(1)

    try:
        summary = resolve_run_mode(
            flow_service, target_branch, instructions, resolved_plan, skill
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
        ensure_plan_file_exists(plan_file, branch=summary.branch or target_branch)
    except FileNotFoundError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    execute_manual_run(
        config=config,
        branch=target_branch,
        issue_number=issue_number,
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
        Optional[str],
        typer.Option(
            "--plan",
            "-p",
            help="Plan reference: file path or '@plan' to use flow's plan_ref",
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
