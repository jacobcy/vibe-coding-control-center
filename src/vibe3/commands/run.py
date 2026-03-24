"""Run command - Execute implementation plans using codeagent-wrapper."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import ReviewAgentOptions
from vibe3.services.flow_service import FlowService
from vibe3.services.label_integration import transition_to_in_progress
from vibe3.services.review_runner import (
    format_agent_actor,
    resolve_actor_backend_model,
    run_review_agent,
)
from vibe3.services.run_context_builder import build_run_context
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="run",
    help="Execute implementation plans using codeagent-wrapper",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]
_DRY_RUN_OPT = Annotated[
    bool,
    typer.Option("--dry-run", help="Print command and prompt without executing"),
]
_AGENT_OPT = Annotated[
    Optional[str],
    typer.Option(
        "--agent", help="Override agent preset (e.g., executor, executor-pro)"
    ),
]
_BACKEND_OPT = Annotated[
    Optional[str],
    typer.Option("--backend", help="Override backend (claude, codex)"),
]
_MODEL_OPT = Annotated[
    Optional[str],
    typer.Option("--model", help="Override model (e.g., claude-3-opus)"),
]


def _get_agent_options(
    config: VibeConfig,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> ReviewAgentOptions:
    """Build agent options with CLI override support.

    Priority:
    1. CLI --agent: use agent preset (ignore config backend/model)
    2. CLI --backend/--model: use backend/model directly
    3. Config: use config backend/model if set, else agent preset
    """
    run_config = getattr(config, "run", None)
    config_agent = None
    config_backend = None
    config_model = None

    if run_config and hasattr(run_config, "agent_config"):
        ac = run_config.agent_config
        config_agent = ac.agent if hasattr(ac, "agent") else None
        config_backend = ac.backend if hasattr(ac, "backend") else None
        config_model = ac.model if hasattr(ac, "model") else None

    # CLI --agent takes precedence over everything
    if agent:
        return ReviewAgentOptions(agent=agent, backend=None, model=None)

    # CLI --backend takes precedence over config
    if backend:
        return ReviewAgentOptions(
            agent=None, backend=backend, model=model or config_model
        )

    # Use config values
    if config_backend:
        return ReviewAgentOptions(
            agent=None, backend=config_backend, model=config_model
        )

    # Fallback to agent preset
    return ReviewAgentOptions(
        agent=config_agent or "executor",
        backend=None,
        model=None,
    )


def _get_handoff_dir() -> Path:
    """Get handoff directory for current branch."""
    git = GitClient()
    git_dir = git.get_git_common_dir()
    branch = git.get_current_branch()
    handoff_dir = get_branch_handoff_dir(git_dir, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    return handoff_dir


def _record_run_event(
    run_content: str,
    options: ReviewAgentOptions,
    plan_file: str,
    session_id: str | None = None,
) -> Path | None:
    """Record run execution to handoff.

    Args:
        run_content: The run content to save
        options: ReviewAgentOptions with agent/backend/model
        plan_file: Path to the plan file being executed
        session_id: Optional session ID from codeagent-wrapper
    """
    git = GitClient()
    try:
        branch = git.get_current_branch()
    except Exception:
        return None

    handoff_dir = _get_handoff_dir()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    run_file = handoff_dir / f"run-{timestamp}.md"

    run_file.write_text(run_content, encoding="utf-8")

    actor = format_agent_actor(options)
    backend, model = resolve_actor_backend_model(options)

    refs: dict[str, str] = {
        "ref": str(run_file),
        "plan_ref": plan_file,
        "backend": backend,
    }
    if model:
        refs["model"] = model
    if session_id:
        refs["session_id"] = session_id

    store = SQLiteClient()
    store.add_event(
        branch,
        "handoff_run",
        actor,
        detail=f"Run completed: {run_file.name}",
        refs=refs,
    )
    store.update_flow_state(
        branch,
        report_ref=str(run_file),
        executor_actor=actor,
        executor_session_id=session_id,
    )

    return run_file


def _run_execution(
    plan_file: str,
    config: VibeConfig,
    dry_run: bool,
    instructions: str | None,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    log = logger.bind(domain="run", plan_file=plan_file)

    # Load existing session_id if available
    git = GitClient()
    try:
        branch = git.get_current_branch()
        flow_status = FlowService().get_flow_status(branch)
        session_id = flow_status.executor_session_id if flow_status else None
    except Exception:
        session_id = None

    log.info("Building run context")
    prompt_file_content = build_run_context(plan_file, config)

    task = instructions
    if instructions:
        log.info("Using custom task message")
        typer.echo(
            f"-> Guidance: {instructions[:60]}{'...' if len(instructions) > 60 else ''}"
        )

    run_config = getattr(config, "run", None)
    if not task and run_config and hasattr(run_config, "run_prompt"):
        task = run_config.run_prompt

    options = _get_agent_options(config, agent, backend, model)

    log.info(
        "Running execution agent",
        agent=options.agent,
        backend=options.backend,
        model=options.model,
        session_id=session_id,
    )
    typer.echo(f"-> Executing plan with {options.agent or options.backend}...")
    result = run_review_agent(
        prompt_file_content, options, task=task, dry_run=dry_run, session_id=session_id
    )

    if dry_run:
        return

    run_content = result.stdout
    effective_session_id = result.session_id or session_id
    run_file = _record_run_event(
        run_content, options, plan_file, session_id=effective_session_id
    )
    if run_file:
        typer.echo(f"-> Run saved: {run_file}")


def _find_skill_file(skill_name: str) -> Path | None:
    """Find SKILL.md for a named skill under skills/ directory.

    Searches from the git root upward to locate skills/<name>/SKILL.md.
    """
    try:
        git = GitClient()
        repo_root = Path(git.get_git_common_dir()).parent
    except Exception:
        repo_root = Path.cwd()

    candidate = repo_root / "skills" / skill_name / "SKILL.md"
    if candidate.exists():
        return candidate

    # Also check worktree root
    cwd_candidate = Path.cwd() / "skills" / skill_name / "SKILL.md"
    if cwd_candidate.exists():
        return cwd_candidate

    return None


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

    task = instructions or f"Execute skill: {skill_name}"
    options = _get_agent_options(config, agent, backend, model)

    typer.echo(f"-> Running skill with {options.agent or options.backend}...")
    result = run_review_agent(skill_content, options, task=task, dry_run=dry_run)

    if dry_run:
        return

    # Record as handoff_run event
    git = GitClient()
    try:
        branch = git.get_current_branch()
        handoff_dir = _get_handoff_dir()
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run_file = handoff_dir / f"skill-{skill_name}-{timestamp}.md"
        run_file.write_text(result.stdout, encoding="utf-8")

        actor = format_agent_actor(options)
        backend_val, model_val = resolve_actor_backend_model(options)
        refs: dict[str, str] = {
            "ref": str(run_file),
            "skill": skill_name,
            "backend": backend_val,
        }
        if model_val:
            refs["model"] = model_val

        store = SQLiteClient()
        store.add_event(
            branch, "handoff_run", actor, detail=f"Skill run: {skill_name}", refs=refs
        )
        typer.echo(f"-> Run saved: {run_file}")
    except Exception as e:
        logger.bind(domain="run").warning(f"Failed to record skill run event: {e}")


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
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Alias for --plan (deprecated)"),
    ] = None,
    skill: Annotated[
        Optional[str],
        typer.Option("--skill", "-s", help="Run a skill from skills/<name>/SKILL.md"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Execute implementation plan or skill using codeagent-wrapper.

    Default: runs current flow's plan_ref.
    Use --plan to specify a plan file, or --skill to run a project skill.
    """
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()

    # --skill mode
    if skill:
        _run_skill(skill, instructions, config, dry_run, agent, backend, model)
        return

    # --plan / --file / flow plan_ref mode
    resolved_file = plan or file
    if resolved_file is None:
        git = GitClient()
        branch = git.get_current_branch()
        flow = FlowService().get_flow_status(branch)
        if not flow or not flow.plan_ref:
            typer.echo(
                "Error: Current flow has no plan_ref.\n"
                "Use 'vibe3 run --plan <file>' or 'vibe3 run --skill <name>'.",
                err=True,
            )
            raise typer.Exit(1)
        resolved_file = Path(flow.plan_ref)
        typer.echo(f"-> Using flow plan: {resolved_file}")

    plan_file = str(resolved_file)
    log = logger.bind(domain="run", action="run", plan_file=plan_file)
    log.info("Starting plan execution")
    typer.echo(f"-> Execute: {plan_file}")

    _run_execution(plan_file, config, dry_run, instructions, agent, backend, model)

    git = GitClient()
    branch = git.get_current_branch()
    flow = FlowService().get_flow_status(branch)
    if not dry_run and flow and flow.task_issue_number:
        result = transition_to_in_progress(flow.task_issue_number)
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
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Alias for --plan (deprecated)"),
    ] = None,
    skill: Annotated[
        Optional[str],
        typer.Option("--skill", "-s", help="Run a skill from skills/<name>/SKILL.md"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    run_command(
        instructions,
        plan,
        file,
        skill,
        trace,
        dry_run,
        agent,
        backend,
        model,
    )
