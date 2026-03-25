"""Helper functions for plan command."""

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.models.agent_execution import AgentExecutionRequest
from vibe3.models.review_runner import ReviewAgentOptions
from vibe3.services.agent_execution_service import execute_agent, load_session_id
from vibe3.services.handoff_event_service import (
    create_handoff_artifact,
    persist_handoff_event,
)
from vibe3.services.review_runner import (
    format_agent_actor,
    resolve_actor_backend_model,
)

if TYPE_CHECKING:
    from vibe3.models.plan import PlanRequest


def get_agent_options(
    config: VibeConfig,
    agent: str | None,
    backend: str | None,
    model: str | None,
    section: Literal["plan", "run"] = "plan",
) -> ReviewAgentOptions:
    """Build agent options with CLI override support.

    Priority:
    1. CLI --agent: use agent preset (ignore config backend/model)
    2. CLI --backend/--model: use backend/model directly
    3. Config: use config backend/model if set, else agent preset
    """
    if section not in {"plan", "run"}:
        raise ValueError(f"Unsupported section: {section}")

    target_config = getattr(config, section, None)
    config_agent = None
    config_backend = None
    config_model = None

    if target_config and hasattr(target_config, "agent_config"):
        ac = target_config.agent_config
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

    # Use config agent preset if available (preferred over backend/model)
    if config_agent:
        return ReviewAgentOptions(agent=config_agent, backend=None, model=None)

    # Fallback to config backend/model
    if config_backend:
        return ReviewAgentOptions(
            agent=None, backend=config_backend, model=config_model
        )

    # No configuration found - raise error
    raise ValueError(
        f"No agent configuration found for '{section}' command. "
        f"Please either:\n"
        f"  1. Configure agent_config in config/settings.yaml under '{section}:' section, or\n"
        f"  2. Use --agent, --backend, or --model CLI options"
    )


def record_plan_event(
    plan_content: str,
    options: ReviewAgentOptions,
    session_id: str | None = None,
) -> Path | None:
    """Record plan execution to handoff.

    Args:
        plan_content: The plan content to save
        options: ReviewAgentOptions with agent/backend/model
        session_id: Optional session ID from codeagent-wrapper
    """
    artifact = create_handoff_artifact("plan", plan_content)
    if artifact is None:
        return None
    branch, plan_file = artifact

    actor = format_agent_actor(options)
    backend, model = resolve_actor_backend_model(options)

    refs: dict[str, str] = {
        "ref": str(plan_file),
        "backend": backend,
    }
    if model:
        refs["model"] = model
    if session_id:
        refs["session_id"] = session_id

    persist_handoff_event(
        branch=branch,
        event_type="handoff_plan",
        actor=actor,
        detail=f"Plan generated: {plan_file.name}",
        refs=refs,
        flow_state_updates={
            "plan_ref": str(plan_file),
            "planner_actor": actor,
            "planner_session_id": session_id,
        },
    )

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
) -> None:
    """Execute plan generation."""
    from vibe3.models.plan import PlanRequest

    if not isinstance(request, PlanRequest):
        raise TypeError(f"Expected PlanRequest, got {type(request)}")

    log = logger.bind(domain="plan", scope=request.scope.kind)

    session_id = load_session_id("planner")

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
        session_id=session_id,
    )
    outcome = execute_agent(
        AgentExecutionRequest(
            prompt_file_content=prompt_file_content,
            options=options,
            task=task,
            dry_run=dry_run,
            session_id=session_id,
        )
    )

    if dry_run:
        return

    plan_content = outcome.result.stdout
    plan_file = record_plan_event(
        plan_content,
        options,
        session_id=outcome.effective_session_id,
    )
    if plan_file:
        import typer

        typer.echo(f"-> Plan saved: {plan_file}")
