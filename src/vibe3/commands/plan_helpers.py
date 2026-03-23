"""Helper functions for plan command."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.services.review_runner import ReviewAgentOptions, format_agent_actor
from vibe3.utils.git_helpers import get_branch_handoff_dir

if TYPE_CHECKING:
    from vibe3.models.plan import PlanRequest


def get_agent_options(
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

    # Agent and backend are mutually exclusive
    selected_backend = backend or config_backend
    selected_model = model or config_model
    selected_agent = None

    if selected_backend is None:
        selected_agent = agent or config_agent or "planner"

    return ReviewAgentOptions(
        agent=selected_agent,
        backend=selected_backend,
        model=selected_model,
    )


def get_handoff_dir() -> Path:
    """Get handoff directory for current branch."""
    git = GitClient()
    git_dir = git.get_git_common_dir()
    branch = git.get_current_branch()
    handoff_dir = get_branch_handoff_dir(git_dir, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    return handoff_dir


def record_plan_event(
    plan_content: str,
    options: ReviewAgentOptions,
) -> Path | None:
    """Record plan execution to handoff.

    Args:
        plan_content: The plan content to save
        options: ReviewAgentOptions with agent/backend/model
    """
    git = GitClient()
    try:
        branch = git.get_current_branch()
    except Exception:
        return None

    handoff_dir_ = get_handoff_dir()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    plan_file = handoff_dir_ / f"plan-{timestamp}.md"

    plan_file.write_text(plan_content, encoding="utf-8")

    actor = format_agent_actor(options)

    store = SQLiteClient()
    store.add_event(
        branch,
        "handoff_plan",
        actor,
        detail=f"Plan generated: {plan_file.name}",
        refs={
            "ref": str(plan_file),
            "backend": options.backend or options.agent,
            "model": options.model,
        },
    )
    store.update_flow_state(branch, plan_ref=str(plan_file), planner_actor=actor)

    return plan_file


def run_plan(
    request: "PlanRequest",
    config: VibeConfig,
    dry_run: bool,
    message: str | None,
    agent: str | None,
    backend: str | None,
    model: str | None,
    build_plan_context_func: Callable,
    run_review_agent_func: Callable,
) -> None:
    """Execute plan generation."""
    from vibe3.models.plan import PlanRequest

    if not isinstance(request, PlanRequest):
        raise TypeError(f"Expected PlanRequest, got {type(request)}")

    log = logger.bind(domain="plan", scope=request.scope.kind)

    log.info("Building plan context")
    prompt_file_content = build_plan_context_func(request, config)

    task = message
    if message:
        log.info("Using custom task message")

    plan_config = getattr(config, "plan", None)
    if not task and plan_config and hasattr(plan_config, "plan_prompt"):
        task = plan_config.plan_prompt

    options = get_agent_options(config, agent, backend, model)

    log.info(
        "Running plan agent",
        agent=options.agent,
        backend=options.backend,
        model=options.model,
    )
    result = run_review_agent_func(
        prompt_file_content, options, task=task, dry_run=dry_run
    )

    if dry_run:
        return

    plan_content = result.stdout
    plan_file = record_plan_event(plan_content, options)
    if plan_file:
        import typer

        typer.echo(f"-> Plan saved to: {plan_file}")

    import typer

    typer.echo("\n" + plan_content)
