"""Run command."""

import os
import re
import time
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend, extract_session_id
from vibe3.agents.review_runner import format_agent_actor
from vibe3.agents.run_agent import RunUsecase
from vibe3.agents.run_prompt import make_run_context_builder, make_skill_context_builder
from vibe3.agents.runner import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.agents.session_service import load_session_id
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
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
from vibe3.manager.prompts import render_manager_prompt
from vibe3.manager.worktree_manager import WorktreeManager
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.review_runner import AgentOptions
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
    GitHubClient().add_comment(
        issue_number,
        f"[run] 执行报错，已切换为 state/failed。\n\n原因：{reason}",
    )
    LabelService().confirm_issue_state(
        issue_number,
        IssueState.FAILED,
        actor=actor,
        force=True,
    )


def _comment_and_fail_manager_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:manager",
) -> None:
    GitHubClient().add_comment(
        issue_number,
        f"[manager] 管理执行报错，已切换为 state/failed。\n\n原因：{reason}",
    )
    LabelService().confirm_issue_state(
        issue_number,
        IssueState.FAILED,
        actor=actor,
        force=True,
    )


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
        execution_name = f"vibe3-supervisor-{safe_name}"
        if issue_number is not None:
            execution_name = f"{execution_name}-issue-{issue_number}"
        handle = backend.start_async(
            prompt=plan_text,
            options=options,
            task=run_task,
            execution_name=execution_name,
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
    return OrchestraConfig.from_settings().supervisor_handoff.supervisor_file


def _resolve_manager_launch_cwd(*, use_worktree: bool, session_id: str | None) -> Path:
    """On first --worktree run, launch from main repo root.

    So wrapper worktrees land under shared .worktrees/.
    """
    if not use_worktree or session_id:
        return Path.cwd()
    git_common_dir = Path(GitClient().get_git_common_dir())
    return git_common_dir.parent


def _resolve_manager_branch(
    *,
    store: SQLiteClient,
    issue_number: int,
    current_branch: str,
) -> str:
    """Prefer target issue's task flow branch; fall back to canonical task branch."""
    flows = store.get_flows_by_issue(issue_number, role="task")
    if not isinstance(flows, list) or not flows:
        return f"task/issue-{issue_number}"

    for flow in flows:
        if flow.get("branch") == current_branch:
            return current_branch

    prioritized = sorted(
        flows,
        key=lambda flow: (
            flow.get("flow_status") == "active",
            flow.get("manager_session_id") is not None,
            flow.get("updated_at") or "",
        ),
        reverse=True,
    )
    branch = str(prioritized[0].get("branch") or "").strip()
    return branch or current_branch


def _resolve_manager_agent_options(
    *,
    orchestra_config: OrchestraConfig,
    runtime_config: VibeConfig,
    worktree: bool,
) -> AgentOptions:
    """Resolve agent options from orchestra assignee dispatch config."""
    ad = orchestra_config.assignee_dispatch
    if ad.agent:
        return AgentOptions(
            agent=ad.agent,
            backend=ad.backend,
            model=ad.model,
            worktree=worktree,
        )
    return CodeagentExecutionService(runtime_config).resolve_agent_options(
        "run", worktree=worktree
    )


def _wait_for_async_session_id(
    log_path: Path, *, timeout_seconds: float = 3.0
) -> str | None:
    """Best-effort poll async output and wrapper log for session id."""
    wrapper_log_path: Path | None = None
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if log_path.exists():
            try:
                repo_log_text = log_path.read_text()
            except OSError:
                repo_log_text = ""
            session_id = extract_session_id(repo_log_text)
            if session_id:
                return session_id

            if wrapper_log_path is None:
                match = re.search(
                    r"Log:\s*(\S+codeagent-wrapper-\d+\.log)",
                    repo_log_text,
                )
                if match:
                    wrapper_log_path = Path(match.group(1))

        if wrapper_log_path and wrapper_log_path.exists():
            try:
                wrapper_log_text = wrapper_log_path.read_text()
            except OSError:
                wrapper_log_text = ""
            session_id = extract_session_id(wrapper_log_text)
            if session_id:
                return session_id
        time.sleep(0.1)
    return None


def _resolve_manager_execution_cwd(
    *,
    orchestra_config: OrchestraConfig,
    issue_number: int,
    target_branch: str,
    current_branch: str,
    use_worktree: bool,
    session_id: str | None,
) -> tuple[Path, bool]:
    """Resolve cwd: reuse existing scene if available, otherwise wrapper worktree."""
    if session_id:
        return (
            _resolve_manager_launch_cwd(
                use_worktree=use_worktree,
                session_id=session_id,
            ),
            False,
        )

    if target_branch == current_branch:
        return (
            _resolve_manager_launch_cwd(
                use_worktree=use_worktree,
                session_id=session_id,
            ),
            False,
        )

    repo_root = Path(GitClient().get_git_common_dir()).parent
    manager_cwd, _ = WorktreeManager(orchestra_config, repo_root).resolve_manager_cwd(
        issue_number,
        target_branch,
    )
    if manager_cwd is not None:
        return manager_cwd, False

    return (
        _resolve_manager_launch_cwd(
            use_worktree=use_worktree,
            session_id=session_id,
        ),
        use_worktree,
    )


def _run_manager_issue_mode(
    *,
    issue_number: int,
    dry_run: bool,
    async_mode: bool,
    worktree: bool,
    fresh_session: bool = False,
) -> None:
    """Internal manager execution entrypoint."""
    orchestra_config = OrchestraConfig.from_settings()
    issue_payload = GitHubClient().view_issue(issue_number, repo=orchestra_config.repo)
    if not isinstance(issue_payload, dict):
        if issue_payload == "network_error":
            typer.echo(
                (
                    f"Error: Unable to load issue #{issue_number} for manager run "
                    "(GitHub read timed out or auth/network is unavailable)."
                ),
                err=True,
            )
        else:
            typer.echo(
                f"Error: Unable to load issue #{issue_number} for manager run.",
                err=True,
            )
        raise typer.Exit(1)

    issue = IssueInfo.from_github_payload(issue_payload)
    if issue is None:
        title = str(issue_payload.get("title") or f"Issue {issue_number}")
        labels = [
            label.get("name", "")
            for label in issue_payload.get("labels", [])
            if isinstance(label, dict)
        ]
        issue = IssueInfo(number=issue_number, title=title, labels=labels)

    runtime_config = VibeConfig.get_defaults()
    store = SQLiteClient()
    current_branch = GitClient().get_current_branch()
    branch = _resolve_manager_branch(
        store=store,
        issue_number=issue_number,
        current_branch=current_branch,
    )
    session_id = None if fresh_session else load_session_id("manager", branch=branch)
    launch_cwd, effective_worktree = _resolve_manager_execution_cwd(
        orchestra_config=orchestra_config,
        issue_number=issue_number,
        target_branch=branch,
        current_branch=current_branch,
        use_worktree=worktree,
        session_id=session_id,
    )
    options = _resolve_manager_agent_options(
        orchestra_config=orchestra_config,
        runtime_config=runtime_config,
        worktree=effective_worktree,
    )
    actor = format_agent_actor(options)
    backend = CodeagentBackend()
    rendered = render_manager_prompt(orchestra_config, issue)
    prompt = rendered.rendered_text
    manager_task = (
        f"Manage issue #{issue_number}: {issue.title}\n"
        "Act as the manager state controller for this issue. "
        "Inspect the scene, read issue comments and handoff, update labels/comments/"
        "handoff when allowed, and stop when the current state rule requires exit."
    )

    if async_mode and not dry_run:
        try:
            handle = backend.start_async(
                prompt=prompt,
                options=options,
                task=manager_task,
                session_id=session_id,
                execution_name=f"vibe3-manager-issue-{issue_number}",
                cwd=launch_cwd,
                env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            )
        except BaseException as exc:
            store.add_event(
                branch,
                "manager_failed",
                actor,
                detail=f"Manager execution failed for issue #{issue_number}: {exc}",
                refs={"issue": str(issue_number), "reason": str(exc)},
            )
            _comment_and_fail_manager_issue(
                issue_number=issue_number,
                reason=f"manager async start failed: {exc}",
            )
            raise typer.Exit(1) from exc
        updates: dict[str, object] = {"latest_actor": actor}
        effective_session_id = session_id or _wait_for_async_session_id(
            handle.log_path,
            timeout_seconds=30.0,
        )
        if effective_session_id:
            updates["manager_session_id"] = effective_session_id
        store.update_flow_state(branch, **updates)
        store.add_event(
            branch,
            "manager_started",
            actor,
            detail=f"Manager execution started for issue #{issue_number}",
            refs={
                "issue": str(issue_number),
                "tmux_session": handle.tmux_session,
                "log": str(handle.log_path),
            },
        )
        typer.echo(f"-> Manager run: issue #{issue_number}")
        typer.echo(f"Tmux session: {handle.tmux_session}")
        typer.echo(f"Session log: {handle.log_path}")
        return

    try:
        result = backend.run(
            prompt=prompt,
            options=options,
            task=manager_task,
            dry_run=dry_run,
            session_id=session_id,
            cwd=launch_cwd,
        )
    except BaseException as exc:
        store.add_event(
            branch,
            "manager_failed",
            actor,
            detail=f"Manager execution failed for issue #{issue_number}: {exc}",
            refs={"issue": str(issue_number), "reason": str(exc)},
        )
        _comment_and_fail_manager_issue(
            issue_number=issue_number,
            reason=f"manager sync execution failed: {exc}",
        )
        raise

    effective_session_id = result.session_id or session_id
    sync_updates: dict[str, object] = {"latest_actor": actor}
    if effective_session_id:
        sync_updates["manager_session_id"] = effective_session_id
    store.update_flow_state(branch, **sync_updates)
    if not result.is_success():
        store.add_event(
            branch,
            "manager_failed",
            actor,
            detail=f"Manager execution failed for issue #{issue_number}",
            refs={"issue": str(issue_number), "status": "failed"},
        )
        _comment_and_fail_manager_issue(
            issue_number=issue_number,
            reason=getattr(result, "stderr", "") or "manager exited with failure",
        )
        raise typer.Exit(1)

    store.add_event(
        branch,
        "manager_completed",
        actor,
        detail=f"Manager execution completed for issue #{issue_number}",
        refs={"issue": str(issue_number), "status": "completed"},
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
