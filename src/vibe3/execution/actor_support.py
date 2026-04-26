"""Shared actor formatting helpers for execution and handoff."""

from typing import Any

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


def extract_role_from_actor(actor: str) -> str:
    """Extract role from actor string.

    Actor format examples:
    - "manager" -> "manager"
    - "planner" -> "planner"
    - "reviewer" -> "reviewer"
    - "executor" -> "executor"
    - "claude/claude-sonnet-4-6" -> "agent"
    - "plan/claude/claude-sonnet-4-6" -> "plan"
    - "run/gemini/gemini-pro" -> "run"

    Args:
        actor: Actor identifier

    Returns:
        Role string
    """
    # Known roles (full names)
    known_roles = {"manager", "planner", "executor", "reviewer"}
    if actor in known_roles:
        return actor

    # Role prefix (e.g., "role/backend" or "role/backend/model")
    if "/" in actor:
        prefix = actor.split("/", 1)[0]
        # Full role names
        if prefix in known_roles:
            return prefix
        # Short aliases (plan -> planner, run -> executor, review -> reviewer)
        role_aliases = {
            "plan": "planner",
            "run": "executor",
            "review": "reviewer",
        }
        if prefix in role_aliases:
            return role_aliases[prefix]

    # Default to "agent"
    return "agent"


def infer_role_from_flow_state(
    store: Any,
    branch: str,
    actor: str,
) -> str:
    """Infer role from flow state by matching actor against role-specific actor fields.

    This function attempts to determine which role (planner/executor/reviewer)
    a given actor is associated with in the current flow.

    Args:
        store: SQLiteClient instance for database access
        branch: Branch name for flow state lookup
        actor: Actor identifier (e.g., "claude/claude-sonnet-4-6")

    Returns:
        Role string: "planner", "executor", "reviewer", or "unknown"
    """
    if not actor or not store or not branch:
        return "unknown"

    try:
        flow_data_raw = store.get_flow_state(branch)
        flow_data = flow_data_raw if isinstance(flow_data_raw, dict) else {}
    except Exception:
        # Database access failed; return unknown rather than crash
        return "unknown"

    if not flow_data:
        return "unknown"

    # Normalize actor for comparison
    normalized_actor = actor.strip().lower()

    # Check role-specific actor fields
    role_actor_map = {
        "planner_actor": "planner",
        "executor_actor": "executor",
        "reviewer_actor": "reviewer",
    }

    for field, role in role_actor_map.items():
        field_value = flow_data.get(field)
        if field_value and isinstance(field_value, str):
            if field_value.strip().lower() == normalized_actor:
                return role

    # Could not determine role from flow state
    return "unknown"
