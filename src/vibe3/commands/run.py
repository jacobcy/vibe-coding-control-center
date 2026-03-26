"""Run command - Execute implementation plans using codeagent-wrapper."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.command_options import (
    _AGENT_OPT,
    _BACKEND_OPT,
    _DRY_RUN_OPT,
    _MODEL_OPT,
    _TRACE_OPT,
    ensure_flow_for_current_branch,
)
from vibe3.commands.plan_helpers import get_agent_options
from vibe3.config.settings import VibeConfig
from vibe3.services.agent_execution_service import execute_agent, load_session_id
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)
from vibe3.services.label_integration import transition_to_in_progress
from vibe3.services.run_context_builder import build_run_context
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
    log = logger.bind(domain="run", plan_file=plan_file or "(lightweight)")

    session_id = load_session_id("executor")

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

    options = get_agent_options(  # type: ignore[call-arg]
        config,
        agent,
        backend,
        model,
        section="run",
    )

    log.info(
        "Running execution agent",
        agent=options.agent,
        backend=options.backend,
        model=options.model,
        session_id=session_id,
    )
    typer.echo(f"-> Executing plan with {options.agent or options.backend}...")
    result = execute_agent(
        options,
        prompt_file_content,
        task=task,
        dry_run=dry_run,
        session_id=session_id,
    )

    if dry_run:
        return

    effective_session_id = result.session_id or session_id
    run_content = result.stdout
    run_file = record_handoff_unified(
        HandoffRecord(
            kind="run",
            content=run_content,
            options=options,
            session_id=effective_session_id,
            metadata={"plan_ref": plan_file} if plan_file else None,
        )
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
    options = get_agent_options(  # type: ignore[call-arg]
        config,
        agent,
        backend,
        model,
        section="run",
    )

    typer.echo(f"-> Running skill with {options.agent or options.backend}...")
    session_id = load_session_id("executor")

    result = execute_agent(
        options,
        skill_content,
        task=task,
        dry_run=dry_run,
        session_id=session_id,
    )

    if dry_run:
        return

    effective_session_id = result.session_id or session_id
    run_file = record_handoff_unified(
        HandoffRecord(
            kind="run",
            content=result.stdout,
            options=options,
            session_id=effective_session_id,
            metadata={"skill": skill_name},
        )
    )
    if run_file:
        typer.echo(f"-> Run saved: {run_file}")


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
    flow_service, branch = ensure_flow_for_current_branch()

    # --skill mode
    if skill:
        _run_skill(skill, instructions, config, dry_run, agent, backend, model)
        return

    # Determine execution mode
    resolved_file = plan or file

    if resolved_file:
        # Explicit plan file provided
        plan_file = str(resolved_file)
        log = logger.bind(domain="run", action="run", plan_file=plan_file)
        log.info("Starting plan execution")
        typer.echo(f"-> Execute: {plan_file}")
    elif instructions:
        # Lightweight mode: only instructions
        plan_file = None
        log = logger.bind(domain="run", action="run", plan_file="(lightweight)")
        log.info("Starting lightweight execution")
        typer.echo("-> Lightweight mode: running with instructions only")
        typer.echo(
            f"-> Task: {instructions[:60]}{'...' if len(instructions) > 60 else ''}"
        )
    else:
        # Try to use flow's plan_ref
        flow = flow_service.get_flow_status(branch)
        if flow and flow.plan_ref:
            plan_file = str(flow.plan_ref)
            log = logger.bind(domain="run", action="run", plan_file=plan_file)
            log.info("Starting plan execution from flow")
            typer.echo(f"-> Using flow plan: {plan_file}")
        else:
            typer.echo(
                "Error: No plan specified.\n"
                "Use one of:\n"
                "  vibe3 run <instructions>        # Lightweight mode\n"
                "  vibe3 run --plan <file>         # With plan file\n"
                "  vibe3 run --skill <name>        # With skill",
                err=True,
            )
            raise typer.Exit(1)

    _run_execution(plan_file, config, dry_run, instructions, agent, backend, model)

    flow = flow_service.get_flow_status(branch)
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
