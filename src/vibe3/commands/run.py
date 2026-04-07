"""Run command."""

from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
from loguru import logger

from vibe3.agents.run_agent import RunUsecase
from vibe3.agents.run_prompt import make_run_context_builder, make_skill_context_builder
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
from vibe3.manager.manager_run_service import run_manager_issue_mode as _svc_run_manager
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.supervisor_run_service import (
    resolve_issue_supervisor_file as _svc_resolve_supervisor_file,
)
from vibe3.orchestra.supervisor_run_service import (
    run_supervisor_mode as _svc_run_supervisor,
)
from vibe3.services.authoritative_ref_gate import (
    require_authoritative_ref as _svc_require_authoritative_ref,
)
from vibe3.services.issue_failure_service import (
    block_executor_noop_issue as _svc_block_executor_noop,
)
from vibe3.services.issue_failure_service import (
    fail_executor_issue as _svc_fail_executor,
)
from vibe3.services.label_service import LabelService
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
    worktree: bool,
    handoff_metadata: dict[str, object] | None,
) -> object:
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
    _svc_fail_executor(issue_number=issue_number, reason=reason, actor=actor)


def _ensure_plan_file_exists(plan_file: str | None) -> None:
    if not plan_file:
        return
    if Path(plan_file).exists():
        return
    raise FileNotFoundError(f"Plan file not found: {plan_file}")


def _run_supervisor_mode(
    *,
    supervisor_file: str,
    issue_number: int | None,
    dry_run: bool,
    async_mode: bool,
) -> None:
    _svc_run_supervisor(
        supervisor_file=supervisor_file,
        issue_number=issue_number,
        dry_run=dry_run,
        async_mode=async_mode,
    )


def _resolve_issue_supervisor_file() -> str:
    return _svc_resolve_supervisor_file()


def _run_manager_issue_mode(
    *,
    issue_number: int,
    dry_run: bool,
    async_mode: bool,
    worktree: bool,
    fresh_session: bool = False,
) -> None:
    _svc_run_manager(
        issue_number=issue_number,
        dry_run=dry_run,
        async_mode=async_mode,
        worktree=worktree,
        fresh_session=fresh_session,
    )


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
    supervisor: Annotated[
        Optional[str],
        typer.Option(
            "--supervisor",
            help="Run a supervisor markdown file as one-shot governance input",
        ),
    ] = None,
    issue: Annotated[
        Optional[int],
        typer.Option(
            "--issue",
            help=(
                "Process a governance issue using the configured "
                "supervisor handoff prompt"
            ),
        ),
    ] = None,
    manager_issue: Annotated[
        Optional[int],
        typer.Option("--manager-issue", hidden=True),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    async_mode: _ASYNC_OPT = True,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
    worktree: _WORKTREE_OPT = False,
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

    if manager_issue is not None:
        _run_manager_issue_mode(
            issue_number=manager_issue,
            dry_run=dry_run,
            async_mode=async_mode,
            worktree=worktree,
            fresh_session=fresh_session,
        )
        return

    if issue is not None and any(
        value is not None for value in (plan, skill, supervisor)
    ):
        typer.echo(
            "Error: --issue cannot be combined with --plan, --skill, or --supervisor.",
            err=True,
        )
        raise typer.Exit(1)

    if issue is not None:
        _run_supervisor_mode(
            supervisor_file=_resolve_issue_supervisor_file(),
            issue_number=issue,
            dry_run=dry_run,
            async_mode=async_mode,
        )
        return

    if supervisor:
        _run_supervisor_mode(
            supervisor_file=supervisor,
            issue_number=issue,
            dry_run=dry_run,
            async_mode=async_mode,
        )
        return

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
            context_builder=make_skill_context_builder(skill_content),
            dry_run=dry_run,
            async_mode=async_mode,
            agent=agent,
            backend=backend,
            model=model,
            worktree=worktree,
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

    try:
        _ensure_plan_file_exists(plan_file)
    except FileNotFoundError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    result = _execute_run_command(
        config=config,
        branch=branch,
        instructions=instructions,
        context_builder=make_run_context_builder(plan_file, config),
        dry_run=dry_run,
        async_mode=async_mode,
        agent=agent,
        backend=backend,
        model=model,
        worktree=worktree,
        handoff_metadata={"plan_ref": plan_file} if plan_file else None,
    )

    issue_number = usecase.transition_issue(branch)
    if not dry_run and not async_mode and issue_number:
        if getattr(result, "success", False):
            if not _svc_require_authoritative_ref(
                flow_service=flow_service,
                branch=branch,
                ref_name="report_ref",
                issue_number=int(issue_number),
                reason=(
                    "executor output artifact was saved, but no authoritative "
                    "report_ref was registered. Write a canonical report "
                    "document and run handoff report."
                ),
                actor="agent:run",
                block_issue=_svc_block_executor_noop,
            ):
                typer.echo(
                    "Error: Executor completed without report_ref; "
                    "issue moved to state/blocked",
                    err=True,
                )
                raise typer.Exit(1)
            transition = LabelService().confirm_issue_state(
                int(issue_number),
                IssueState.HANDOFF,
                actor="agent:run",
            )
            if transition == "blocked":
                typer.echo(
                    "Warning: Failed to transition issue state: "
                    "state_transition_blocked",
                    err=True,
                )
        else:
            _comment_and_fail_issue(
                issue_number=int(issue_number),
                reason=getattr(result, "stderr", "") or "executor exited with failure",
                actor="agent:run",
            )
            typer.echo(
                "Error: Executor failed; issue moved to state/failed",
                err=True,
            )
            raise typer.Exit(1)


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
    supervisor: Annotated[
        Optional[str],
        typer.Option(
            "--supervisor",
            help="Run a supervisor markdown file as one-shot governance input",
        ),
    ] = None,
    issue: Annotated[
        Optional[int],
        typer.Option(
            "--issue",
            help="Pass a specific governance issue number to the supervisor task",
        ),
    ] = None,
    manager_issue: Annotated[
        Optional[int],
        typer.Option("--manager-issue", hidden=True),
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

    run_command(
        instructions,
        plan,
        skill,
        supervisor,
        issue,
        manager_issue,
        trace,
        dry_run,
        async_mode,
        agent,
        backend,
        model,
        worktree,
    )
