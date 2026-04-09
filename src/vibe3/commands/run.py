"""Run command."""

import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.agents.run_agent import RunUsecase
from vibe3.agents.run_prompt import make_run_context_builder, make_skill_context_builder
from vibe3.agents.runner import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.clients.sqlite_client import SQLiteClient
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
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="run",
    help="Execute implementation plans using codeagent-wrapper",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


def _find_skill_file(skill_name: str) -> Path | None:
    return RunUsecase.find_skill_file(skill_name)


def _dispatch_async_run_command(
    *,
    branch: str,
    cli_args: list[str],
    issue_number: int | None,
    execution_name: str,
    handoff_metadata: dict[str, object] | None,
) -> None:
    refs: dict[str, str] = {}
    if issue_number is not None:
        refs["issue_number"] = str(issue_number)
    if handoff_metadata:
        refs.update({k: str(v) for k, v in handoff_metadata.items()})
    ExecutionCoordinator(
        OrchestraConfig.from_settings(),
        SQLiteClient(),
    ).dispatch_execution(
        ExecutionRequest(
            role="executor",
            target_branch=branch,
            target_id=issue_number or 0,
            execution_name=execution_name,
            cmd=CodeagentExecutionService.build_self_invocation(cli_args),
            cwd=str(Path.cwd()),
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs=refs,
            actor="agent:run",
            mode="async",
        )
    )


def _ensure_plan_file_exists(plan_file: str | None) -> None:
    if not plan_file:
        return
    if Path(plan_file).exists():
        return
    raise FileNotFoundError(f"Plan file not found: {plan_file}")


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
    no_async: _ASYNC_OPT = False,
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
) -> None:
    """Execute implementation plan or skill."""
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()
    flow_service, branch = ensure_flow_for_current_branch()
    usecase = RunUsecase(flow_service=flow_service)
    issue_number = usecase.transition_issue(branch)

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
        if not dry_run and not no_async:
            _dispatch_async_run_command(
                branch=branch,
                cli_args=[
                    "run",
                    "--skill",
                    skill,
                    *([instructions] if instructions else []),
                ],
                issue_number=int(issue_number) if issue_number else None,
                execution_name=(
                    f"vibe3-executor-issue-{issue_number}"
                    if issue_number
                    else f"vibe3-executor-{branch.replace('/', '-')}"
                ),
                handoff_metadata={"skill": skill},
            )
            return
        command = create_codeagent_command(
            role="executor",
            context_builder=make_skill_context_builder(skill_content),
            task=instructions or f"Execute skill: {skill}",
            dry_run=dry_run,
            handoff_kind="run",
            handoff_metadata={"skill": skill},
            agent=agent,
            backend=backend,
            model=model,
            config=config,
            branch=branch,
        )
        CodeagentExecutionService(config).execute_sync(command)
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

    try:
        _ensure_plan_file_exists(plan_file)
    except FileNotFoundError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    # Build command
    run_prompt = config.run.run_prompt if getattr(config, "run", None) else None
    command = create_codeagent_command(
        role="executor",
        context_builder=make_run_context_builder(plan_file, config),
        task=instructions or run_prompt,
        dry_run=dry_run,
        handoff_kind="run",
        handoff_metadata={"plan_ref": plan_file} if plan_file else None,
        agent=agent,
        backend=backend,
        model=model,
        config=config,
        branch=branch,
    )

    execution_service = CodeagentExecutionService(config)
    if not dry_run and not no_async:
        if skill:
            cli_args = [
                "run",
                "--skill",
                skill,
                *([instructions] if instructions else []),
            ]
        elif summary.mode == "plan":
            cli_args = [
                "run",
                "--plan",
                str(plan_file),
                *([instructions] if instructions else []),
            ]
        elif summary.mode == "lightweight":
            cli_args = ["run", *([instructions] if instructions else [])]
        else:
            cli_args = ["run"]
        _dispatch_async_run_command(
            branch=branch,
            cli_args=cli_args,
            issue_number=int(issue_number) if issue_number else None,
            execution_name=(
                f"vibe3-executor-issue-{issue_number}"
                if issue_number
                else f"vibe3-executor-{branch.replace('/', '-')}"
            ),
            handoff_metadata={"plan_ref": plan_file} if plan_file else None,
        )
        return
    if not dry_run and no_async and issue_number:
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            int(issue_number), branch, flow_service
        )
        try:
            result = execution_service.execute_sync(command)
            if result.success:
                on_success(result)
            else:
                on_failure(Exception(result.stderr or "Execution failed"))
        except Exception as error:
            on_failure(error)
            raise
    else:
        execution_service.execute_sync(command)


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
    no_async: _ASYNC_OPT = False,
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
        no_async,
        agent,
        backend,
        model,
    )
