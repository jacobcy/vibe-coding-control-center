"""Review runner service - executes codeagent-wrapper for code review.

Migrated from vibe3.services.review_runner.
"""

from vibe3.agents.backends.codeagent import (
    DEFAULT_WRAPPER_PATH,
    MODELS_JSON_PATH,
    extract_session_id,
    sync_models_json,
)
from vibe3.models.review_runner import AgentOptions

__all__ = [
    "DEFAULT_WRAPPER_PATH",
    "MODELS_JSON_PATH",
    "extract_session_id",
    "format_agent_actor",
    "resolve_actor_backend_model",
    "sync_models_json",
]


def resolve_actor_backend_model(options: AgentOptions) -> tuple[str, str | None]:
    """Resolve the actual backend and model for database recording.

    Priority:
    1. If backend is provided (CLI override): use backend/model
    2. If only agent is provided: use agent as backend identifier

    Args:
        options: AgentOptions with agent/backend/model

    Returns:
        Tuple of (backend, model) for database recording
    """
    if options.backend:
        return options.backend, options.model
    if options.agent:
        return options.agent, options.model
    return "unknown", None


def format_agent_actor(options: AgentOptions) -> str:
    """Format the actor string for handoff records.

    Actor format: '<backend>/<model>' or '<backend>'
    - backend: either agent preset name or direct backend name
    - model: optional model name

    Args:
        options: AgentOptions with agent/backend/model

    Returns:
        Actor string like 'claude/sonnet' or 'planner' or 'unknown'
    """
    backend, model = resolve_actor_backend_model(options)
    if model:
        return f"{backend}/{model}"
    return backend
