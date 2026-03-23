"""Plan command - Create implementation plans using codeagent-wrapper."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.services.flow_service import FlowService
from vibe3.services.plan_context_builder import build_plan_context
from vibe3.services.review_runner import ReviewAgentOptions, run_review_agent
from vibe3.utils.git_helpers import get_branch_handoff_dir
from vibe3.utils.trace import enable_trace

app = typer.Typer(
    name="plan",
    help="Create implementation plans using codeagent-wrapper",
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
    typer.Option("--agent", help="Override agent preset (e.g., planner, planner-pro)"),
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
    """Build agent options with CLI override support."""
    plan_config = getattr(config, "plan", None)
    config_agent = None
    config_backend = None
    config_model = None

    if plan_config and hasattr(plan_config, "agent_config"):
        ac = plan_config.agent_config
        config_agent = ac.agent if hasattr(ac, "agent") else None
        config_backend = ac.backend if hasattr(ac, "backend") else None
        config_model = ac.model if hasattr(ac, "model") else None

    return ReviewAgentOptions(
        agent=agent or config_agent or "planner",
        backend=backend or config_backend,
        model=model or config_model,
    )


def _get_handoff_dir() -> Path:
    """Get handoff directory for current branch."""
    git = GitClient()
    git_dir = git.get_git_common_dir()
    branch = git.get_current_branch()
    handoff_dir = get_branch_handoff_dir(git_dir, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    return handoff_dir


def _record_plan_event(
    plan_content: str,
    config: VibeConfig,
) -> Path | None:
    """Record plan execution to handoff."""
    git = GitClient()
    try:
        branch = git.get_current_branch()
    except Exception:
        return None

    handoff_dir = _get_handoff_dir()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    plan_file = handoff_dir / f"plan-{timestamp}.md"

    plan_file.write_text(plan_content, encoding="utf-8")

    plan_config = getattr(config, "plan", None)
    agent = "planner"
    model = None
    if plan_config and hasattr(plan_config, "agent_config"):
        ac = plan_config.agent_config
        agent = ac.agent if hasattr(ac, "agent") else "planner"
        model = ac.model if hasattr(ac, "model") else None

    actor = f"{agent}/{model}" if model else agent

    store = SQLiteClient()
    store.add_event(
        branch,
        "handoff_plan",
        actor,
        detail=f"Plan generated: {plan_file.name}",
        refs={"ref": str(plan_file), "agent": agent, "model": model},
    )
    store.update_flow_state(branch, plan_ref=str(plan_file), planner_actor=actor)

    return plan_file


def _run_plan(
    request: PlanRequest,
    config: VibeConfig,
    dry_run: bool,
    message: str | None,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    """Execute plan generation."""
    log = logger.bind(domain="plan", scope=request.scope.kind)

    log.info("Building plan context")
    prompt_file_content = build_plan_context(request, config)

    task = message
    if message:
        log.info("Using custom task message")
        typer.echo(f"-> Guidance: {message[:60]}{'...' if len(message) > 60 else ''}")

    plan_config = getattr(config, "plan", None)
    if not task and plan_config and hasattr(plan_config, "plan_prompt"):
        task = plan_config.plan_prompt

    options = _get_agent_options(config, agent, backend, model)

    log.info(
        "Running plan agent",
        agent=options.agent,
        backend=options.backend,
        model=options.model,
    )
    typer.echo(f"-> Generating plan with {options.agent or options.backend}...")
    result = run_review_agent(prompt_file_content, options, task=task, dry_run=dry_run)

    if dry_run:
        return

    plan_content = result.stdout
    plan_file = _record_plan_event(plan_content, config)
    if plan_file:
        typer.echo(f"-> Plan saved to: {plan_file}")

    typer.echo("\n" + plan_content)


@app.command()
def task(
    issue: Annotated[
        int | None,
        typer.Argument(help="Issue number (default: current flow's task issue)"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    message: _MESSAGE_OPT = None,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Create implementation plan for an issue.

    If no issue number is provided, uses the current flow's task issue.

    Examples:
        vibe3 plan task              # Use current flow's task issue
        vibe3 plan task 42           # Plan for issue #42
        vibe3 plan task 42 --dry-run
        vibe3 plan task 42 -m "Focus on security"
        vibe3 plan task 42 --agent planner-pro
    """
    if trace:
        enable_trace()

    config = VibeConfig.get_defaults()

    if issue is None:
        git = GitClient()
        branch = git.get_current_branch()
        flow = FlowService().get_flow_status(branch)
        if not flow or not flow.task_issue_number:
            typer.echo(
                "Error: No issue number provided and current flow has no task issue.\n"
                "Use 'vibe3 plan task <issue>' or bind a task to the current flow.",
                err=True,
            )
            raise typer.Exit(1)
        issue = flow.task_issue_number
        typer.echo(f"-> Using flow task: Issue #{issue}")

    log = logger.bind(domain="plan", action="task", issue=issue)
    log.info("Starting plan for issue")
    typer.echo(f"-> Plan: Issue #{issue}")

    scope = PlanScope.for_task(issue)
    request = PlanRequest(scope=scope)
    _run_plan(request, config, dry_run, message, agent, backend, model)


@app.command()
def spec(
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Path to spec file"),
    ] = None,
    msg: Annotated[
        Optional[str],
        typer.Option("--msg", help="Spec description"),
    ] = None,
    trace: _TRACE_OPT = False,
    dry_run: _DRY_RUN_OPT = False,
    message: _MESSAGE_OPT = None,
    agent: _AGENT_OPT = None,
    backend: _BACKEND_OPT = None,
    model: _MODEL_OPT = None,
) -> None:
    """Create implementation plan from a specification.

    Provide either --file or --msg (not both).

    Examples:
        vibe3 plan spec --file spec.md
        vibe3 plan spec --msg "Add dark mode support"
        vibe3 plan spec -f spec.md -m "Prioritize performance"
        vibe3 plan spec --msg "Refactor auth" --agent planner-pro
    """
    if trace:
        enable_trace()

    if file and msg:
        typer.echo("Error: Provide either --file or --msg, not both.", err=True)
        raise typer.Exit(1)

    if not file and not msg:
        typer.echo("Error: Provide either --file or --msg.", err=True)
        raise typer.Exit(1)

    config = VibeConfig.get_defaults()

    description = ""
    spec_path = None
    if file:
        if not file.exists():
            typer.echo(f"Error: File not found: {file}", err=True)
            raise typer.Exit(1)
        description = file.read_text(encoding="utf-8")
        spec_path = str(file.resolve())
        typer.echo(f"-> Plan from file: {file}")
    elif msg:
        description = msg
        typer.echo(f"-> Plan: {msg[:60]}{'...' if len(msg) > 60 else ''}")

    if spec_path and not dry_run:
        git = GitClient()
        store = SQLiteClient()
        try:
            branch = git.get_current_branch()
            store.update_flow_state(branch, spec_ref=spec_path)
            store.add_event(branch, "spec_bound", "user", detail=f"Spec bound: {file}")
        except Exception:
            pass

    log = logger.bind(domain="plan", action="spec")
    log.info("Starting plan from spec")

    scope = PlanScope.for_spec(description)
    request = PlanRequest(scope=scope)
    _run_plan(request, config, dry_run, message, agent, backend, model)
