"""Helper functions for plan command."""

from typing import TYPE_CHECKING, Callable, Literal

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import AgentOptions
from vibe3.services.execution_pipeline import ExecutionRequest, run_execution_pipeline

if TYPE_CHECKING:
    from vibe3.models.plan import PlanRequest


def get_agent_options(
    config: VibeConfig,
    agent: str | None,
    backend: str | None,
    model: str | None,
    section: Literal["plan", "run"] = "plan",
) -> AgentOptions:
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
        return AgentOptions(agent=agent, backend=None, model=None)

    # CLI --backend takes precedence over config
    if backend:
        return AgentOptions(agent=None, backend=backend, model=model or config_model)

    # Use config agent preset if available (preferred over backend/model)
    if config_agent:
        return AgentOptions(agent=config_agent, backend=None, model=None)

    # Fallback to config backend/model
    if config_backend:
        return AgentOptions(agent=None, backend=config_backend, model=config_model)

    # No configuration found - raise error
    raise ValueError(
        f"No agent configuration found for '{section}' command. "
        f"Please either:\n"
        f"  1. Configure agent_config in settings.yaml under '{section}:' section, or\n"
        f"  2. Use --agent, --backend, or --model CLI options"
    )


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

    # Resolve task message
    task = message
    if message:
        log.info("Using custom task message")

    plan_config = getattr(config, "plan", None)
    if not task and plan_config and hasattr(plan_config, "plan_prompt"):
        task = plan_config.plan_prompt

    # Build execution request
    exec_request = ExecutionRequest(
        role="planner",
        context_builder=lambda: build_plan_context_func(request, config),
        options_builder=lambda: get_agent_options(config, agent, backend, model),
        task=task,
        dry_run=dry_run,
        handoff_kind="plan",
    )

    run_execution_pipeline(exec_request)
