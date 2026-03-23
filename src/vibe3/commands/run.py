"""Run command - Execute implementation plans using codeagent-wrapper."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.services.flow_service import FlowService
from vibe3.services.review_runner import ReviewAgentOptions, run_review_agent
from vibe3.services.run_context_builder import build_run_context
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="run",
    help="Execute implementation plans using codeagent-wrapper",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_TRACE_OPT = Annotated[
    bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
]
_DRY_RUN_OPT = Annotated[
    bool,
    typer.Option("--dry-run", help="Print command and prompt without executing"),
]
_MESSAGE_OPT = Annotated[
    Optional[str],
    typer.Option("--message", "-m", help="Additional task guidance"),
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
    run_config = getattr(config, "run", None)
    config_agent = None
    config_backend = None
    config_model = None

    if run_config and hasattr(run_config, "agent_config"):
        ac = run_config.agent_config
        config_agent = ac.agent if hasattr(ac, "agent") else None
        config_backend = ac.backend if hasattr(ac, "backend") else None
        config_model = ac.model if hasattr(ac, "model") else None

    selected_backend = backend or config_backend
    selected_model = model or config_model
    selected_agent = None

    if selected_backend is None:
        selected_agent = agent or config_agent or "executor"

    return ReviewAgentOptions(
        agent=selected_agent,
        backend=selected_backend,
        model=selected_model,
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
    config: VibeConfig,
    plan_file: str,
) -> Path | None:
    """Record run execution to handoff."""
    git = GitClient()
    try:
        branch = git.get_current_branch()
    except Exception:
        return None

    handoff_dir = _get_handoff_dir()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    run_file = handoff_dir / f"run-{timestamp}.md"

    run_file.write_text(run_content, encoding="utf-8")

    run_config = getattr(config, "run", None)
    agent = "executor"
    model = None
    if run_config and hasattr(run_config, "agent_config"):
        ac = run_config.agent_config
        agent = ac.agent if hasattr(ac, "agent") else "executor"
        model = ac.model if hasattr(ac, "model") else None

    actor = f"{agent}/{model}" if model else agent

    store = SQLiteClient()
    store.add_event(
        branch,
        "handoff_run",
        actor,
        detail=f"Run completed: {run_file.name}",
        refs={
            "ref": str(run_file),
            "plan_ref": plan_file,
            "agent": agent,
            "model": model,
        },
    )
    store.update_flow_state(branch, report_ref=str(run_file), executor_actor=actor)

    return run_file


def _run_execution(
    plan_file: str,
    config: VibeConfig,
    dry_run: bool,
    message: str | None,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    log = logger.bind(domain="run", plan_file=plan_file)

    log.info("Building run context")
    prompt_file_content = build_run_context(plan_file, config)

    task = message
    if message:
        log.info("Using custom task message")
        typer.echo(f"-> Guidance: {message[:60]}{'...' if len(message) > 60 else ''}")

    run_config = getattr(config, "run", None)
    if not task and run_config and hasattr(run_config, "run_prompt"):
        task = run_config.run_prompt

    options = _get_agent_options(config, agent, backend, model)

    log.info(
        "Running execution agent",
        agent=options.agent,
        backend=options.backend,
        model=options.model,
    )
    typer.echo(f"-> Executing plan with {options.agent or options.backend}...")
    result = run_review_agent(prompt_file_content, options, task=task, dry_run=dry_run)

    if dry_run:
        return

    run_content = result.stdout
    run_file = _record_run_event(run_content, config, plan_file)
    if run_file:
        typer.echo(f"-> Run output saved to: {run_file}")

    typer.echo("\n" + run_content)


@app.command()
def execute(
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Path to plan file"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    message: _MESSAGE_OPT = None,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()

    if file is None:
        git = GitClient()
        branch = git.get_current_branch()
        flow = FlowService().get_flow_status(branch)
        if not flow or not flow.plan_ref:
            typer.echo(
                "Error: No file provided and current flow has no plan "
                "reference.\nUse 'vibe3 run execute --file plan.md' "
                "or set a plan on the current flow.",
                err=True,
            )
            raise typer.Exit(1)
        file = Path(flow.plan_ref)
        typer.echo(f"-> Using flow plan: {file}")

    plan_file = str(file)
    log = logger.bind(domain="run", action="execute", plan_file=plan_file)
    log.info("Starting plan execution")
    typer.echo(f"-> Execute: {plan_file}")

    _run_execution(plan_file, config, dry_run, message, agent, backend, model)
