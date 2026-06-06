"""Actor normalization utilities for models layer.

This module provides the canonical implementation of normalize_actor,
extracted from vibe3.utils.actor_utils to maintain proper architecture layering.

This is the single source of truth for actor normalization. The utils module
(vibe3.utils.actor_utils) re-exports from here for backward compatibility.

This is a private module (underscore prefix) not part of the public models API.
"""

# Placeholder actors for FLOW OPERATIONS (used in signature_service._is_placeholder).
# These signal "no meaningful actor has claimed this operation."
PLACEHOLDER_ACTORS = {"", "unknown", "server", "system", "workflow"}

# Placeholder actors for DISPLAY / PR BODY (normalize_actor).
# Wider set: also includes generic AI labels that carry no specific identity.
DISPLAY_PLACEHOLDER_ACTORS = frozenset(
    {*PLACEHOLDER_ACTORS, "ai_assistant", "ai-assistant"}
)

# Actor alias → normalized identifier (for display layer).
ACTOR_ALIAS_MAP: dict[str, str] = {
    "agent-claude": "claude",
    "claude-ai": "claude",
    "agent-codex": "codex",
    "openai-code-agent[bot]": "openai",
    "openai-code-agent": "openai",
}


def normalize_actor(actor: str | None) -> str | None:
    """Normalize an actor identifier for display (PR body, UI).

    Handles:
    - ``None`` / empty / whitespace-only → ``None``
    - Placeholder values (unknown, system, workflow, ai-assistant, …) → ``None``
    - Actor aliases (``Agent-Claude``) → standard backend (``claude``)
    - Already-standard format (``claude/sonnet-4.6``) → pass through, trimmed

    This is the single source of truth for actor normalisation at the
    display / PR-body layer.
    """
    if not actor or not actor.strip():
        return None
    key = actor.strip().lower()
    if key in DISPLAY_PLACEHOLDER_ACTORS:
        return None
    if key in ACTOR_ALIAS_MAP:
        return ACTOR_ALIAS_MAP[key]
    return actor.strip()


_PLACEHOLDER_ACTORS = PLACEHOLDER_ACTORS
_DISPLAY_PLACEHOLDER_ACTORS = DISPLAY_PLACEHOLDER_ACTORS
_ACTOR_ALIAS_MAP = ACTOR_ALIAS_MAP
