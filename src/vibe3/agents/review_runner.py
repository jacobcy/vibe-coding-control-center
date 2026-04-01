"""Review runner service - executes codeagent-wrapper for code review.

Migrated from vibe3.services.review_runner.
"""

from vibe3.agents.backends.codeagent import (
    DEFAULT_WRAPPER_PATH,
    MODELS_JSON_PATH,
    CodeagentBackend,
    extract_session_id,
    sync_models_json,
)
from vibe3.models.review_runner import AgentOptions, AgentResult

__all__ = [
    "DEFAULT_WRAPPER_PATH",
    "MODELS_JSON_PATH",
    "extract_session_id",
    "format_agent_actor",
    "resolve_actor_backend_model",
    "run_review_agent",
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


def run_review_agent(
    prompt_file_content: str,
    options: AgentOptions,
    task: str | None = None,
    dry_run: bool = False,
    session_id: str | None = None,
) -> AgentResult:
    """Run a review agent using codeagent-wrapper.

    Args:
        prompt_file_content: Prompt file content (ignored if session_id provided)
        options: Configuration for the agent run
        task: Optional task/instruction (custom message or default)
        dry_run: If True, print command and prompt without executing
        session_id: Optional session ID to resume an existing session

    Returns:
        AgentResult containing exit code, output, and session_id

    Raises:
        AgentExecutionError: If wrapper is missing, times out, or returns non-zero exit

    """
    backend = CodeagentBackend()
    return backend.run(
        prompt=prompt_file_content,
        options=options,
        task=task,
        dry_run=dry_run,
        session_id=session_id,
    )
