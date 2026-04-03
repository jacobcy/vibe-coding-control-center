"""Run command."""

import os
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.run_agent import RunUsecase
from vibe3.agents.run_prompt import (
    make_run_context_builder,
    make_skill_context_builder,
)
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
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.status_service import OrchestraStatusService
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
        worktree=worktree,
        config=config,
        branch=branch,
    )
    CodeagentExecutionService(config).execute(command, async_mode=async_mode)


def _ensure_plan_file_exists(plan_file: str | None) -> None:
    """Fail fast when plan file is missing to avoid noisy run lifecycle writes."""
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
    config = OrchestraConfig.from_settings()
    governance_cfg = config.governance.model_copy(
        update={
            "supervisor_file": supervisor_file,
            "include_supervisor_content": True,
            "dry_run": dry_run,
        }
    )
    config = config.model_copy(update={"governance": governance_cfg})
    service = GovernanceService(
        config=config,
        status_service=OrchestraStatusService(config),
    )
    plan_text = service.render_current_plan()

    if dry_run:
        typer.echo(f"-> Supervisor dry run: {supervisor_file}")
        typer.echo(plan_text)
        return

    runtime_config = VibeConfig.get_defaults()
    options = CodeagentExecutionService(runtime_config).resolve_agent_options("run")
    run_task = _build_supervisor_task(
        config=config,
        issue_number=issue_number,
    ) or (runtime_config.run.run_prompt or "Execute governance supervisor task")
    backend = CodeagentBackend()

    typer.echo(f"-> Supervisor run: {supervisor_file}")
    if async_mode:
        safe_name = Path(supervisor_file).stem.replace("/", "-")
        handle = backend.start_async(
            prompt=plan_text,
            options=options,
            task=run_task,
            execution_name=f"vibe3-supervisor-{safe_name}",
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        )
        typer.echo(f"Tmux session: {handle.tmux_session}")
        typer.echo(f"Session log: {handle.log_path}")
        return

    result = backend.run(
        prompt=plan_text,
        options=options,
        task=run_task,
        dry_run=False,
    )
    if not result.is_success():
        raise typer.Exit(1)


def _build_supervisor_task(
    *,
    config: OrchestraConfig,
    issue_number: int | None,
) -> str | None:
    if issue_number is None:
        return None
    repo_hint = f" in repo {config.repo}" if config.repo else ""
    issue_title = f"issue #{issue_number}"
    issue = GitHubClient().view_issue(issue_number, repo=config.repo)
    if isinstance(issue, dict):
        raw_title = issue.get("title")
        if isinstance(raw_title, str) and raw_title.strip():
            issue_title = raw_title.strip()
    return (
        f"Process governance issue #{issue_number}{repo_hint}: {issue_title}\n"
        "This issue has already been handed to the current supervisor explicitly.\n"
        "Read the issue directly, verify the findings, perform the allowed actions, "
        "comment the outcome on the same issue, and close it when complete."
    )


def _resolve_issue_supervisor_file() -> str:
    """Resolve the configured supervisor file for governance issue execution."""
    return OrchestraConfig.from_settings().supervisor_handoff.supervisor_file


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
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    async_mode: _ASYNC_OPT = True,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
    worktree: _WORKTREE_OPT = False,
) -> None:
    """Execute implementation plan or skill."""
    if trace:
        enable_trace()

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

    _execute_run_command(
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
    if not dry_run and issue_number:
        result = LabelService().confirm_issue_state(
            int(issue_number),
            IssueState.IN_PROGRESS,
            actor="agent:run",
        )
        if result == "blocked":
            typer.echo(
                "Warning: Failed to transition issue state: state_transition_blocked",
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
        trace,
        dry_run,
        async_mode,
        agent,
        backend,
        model,
        worktree,
    )
