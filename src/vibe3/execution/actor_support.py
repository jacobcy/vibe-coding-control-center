"""Shared actor formatting helpers for execution and handoff."""

from vibe3.agents.backends.codeagent_config import resolve_effective_agent_options
from vibe3.exceptions import AgentPresetNotFoundError
from vibe3.models.review_runner import AgentOptions


def resolve_actor_backend_model(options: AgentOptions) -> tuple[str, str | None]:
    """Resolve the actual backend and model for database recording.

    This function ALWAYS returns backend/model, never agent preset names.
    If agent preset cannot be resolved, raises AgentPresetNotFoundError.

    Raises:
        AgentPresetNotFoundError: If agent preset cannot be resolved to backend/model
    """
    try:
        effective = resolve_effective_agent_options(options)
        if effective.backend:
            return effective.backend, effective.model
        # Should never reach here after resolve_effective_agent_options
        raise AgentPresetNotFoundError(
            f"No backend/model available for options: {options}"
        )
    except AgentPresetNotFoundError:
        raise  # Re-raise to propagate to caller


def format_agent_actor(options: AgentOptions) -> str:
    """Format the actor string for handoff records.

    ALWAYS returns backend/model format, never agent preset names.

    Raises:
        AgentPresetNotFoundError: If agent preset cannot be resolved
    """
    backend, model = resolve_actor_backend_model(options)
    if model:
        return f"{backend}/{model}"
    return backend
