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
    load_config_and_validate_model,
    validate_show_prompt_dependency,
)
from vibe3.commands.common import _handle_codeagent_result, enable_method_trace
from vibe3.exceptions import UserError
from vibe3.roles import (
    ensure_plan_file_exists,
    resolve_run_mode,
    resolve_skill_path,
    validate_run_prerequisites,
)
from vibe3.services.flow import FlowService, resolve_branch_arg
from vibe3.services.handoff import resolve_handoff_target

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
    from vibe3.domain import register_event_handlers
    from vibe3.models import ManualRunIntent, publish_and_wait

    register_event_handlers()

    # Load config and validate --model requires backend (CLI or config)
    _config = load_config_and_validate_model("run", agent, backend, model)

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
        summary = resolve_run_mode(
            flow_service, target_branch, instructions, None, skill
        )
        # Publish ManualRunIntent event and wait for result
        from vibe3.commands.common import echo_dry_run_header

        if dry_run:
            echo_dry_run_header(
                "executor", issue_number, target_branch, agent, backend, model
            )

        result = publish_and_wait(
            ManualRunIntent(
                issue_number=issue_number,
                branch=target_branch,
                instructions=instructions,
                plan_file=None,
                skill=skill,
                summary_mode=summary.mode,
                summary_message=summary.message,
                summary_branch=summary.branch,
                dry_run=dry_run,
                no_async=no_async,
                show_prompt=show_prompt,
                agent=agent,
                backend=backend,
                model=model,
                fresh_session=fresh_session,
                publish=publish,
            )
        )

        # Display result
        _handle_codeagent_result(result, "Run")
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

    # Resolve plan file path for actual reading (handles handoff artifacts, worktrees)
    resolved_plan_for_read = plan_file
    if plan_file:
        try:
            resolved_plan_for_read = str(
                resolve_handoff_target(
                    plan_file, branch=summary.branch or target_branch
                )
            )
        except FileNotFoundError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

    # Publish ManualRunIntent event and wait for result
    from vibe3.commands.common import echo_dry_run_header

    if dry_run:
        echo_dry_run_header(
            "executor", issue_number, target_branch, agent, backend, model
        )

    result = publish_and_wait(
        ManualRunIntent(
            issue_number=issue_number,
            branch=target_branch,
            instructions=instructions,
            plan_file=resolved_plan_for_read,
            skill=None,
            summary_mode=summary.mode,
            summary_message=summary.message,
            summary_branch=summary.branch,
            dry_run=dry_run,
            no_async=no_async,
            show_prompt=show_prompt,
            agent=agent,
            backend=backend,
            model=model,
            fresh_session=fresh_session,
            publish=publish,
        )
    )

    # Display result
    _handle_codeagent_result(result, "Run")


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
