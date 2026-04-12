"""Shared actor formatting helpers for execution and handoff."""

from vibe3.models.review_runner import AgentOptions


def resolve_actor_backend_model(options: AgentOptions) -> tuple[str, str | None]:
    """Resolve the actual backend and model for database recording."""
    if options.backend:
        return options.backend, options.model
    if options.agent:
        return options.agent, options.model
    return "unknown", None


def format_agent_actor(options: AgentOptions) -> str:
    """Format the actor string for handoff records."""
    backend, model = resolve_actor_backend_model(options)
    if model:
        return f"{backend}/{model}"
    return backend
