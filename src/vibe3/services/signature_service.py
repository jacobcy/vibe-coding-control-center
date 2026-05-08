"""Unified actor/signature resolution for workflow and flow events."""

from typing import Any

from vibe3.clients.git_client import GitClient
from vibe3.utils.actor_utils import normalize_actor as _normalize_actor_for_display

WORKFLOW_ACTOR = "workflow"
AI_ASSISTANT_ACTORS = {"ai-assistant", "ai_assistant"}

ORCHESTRA_MANAGER = "orchestra:manager"
MANUAL_INITIATOR = "manual"

# Placeholder actors for FLOW OPERATIONS (resolve_actor / _is_placeholder).
# These signal "no meaningful actor has claimed this operation."
_PLACEHOLDER_ACTORS = {"", "unknown", "server", "system", "workflow"}


class SignatureService:
    """Unified actor resolution and normalization.

    Two primary use cases:
    - **Flow operations** (resolve_actor / resolve_for_branch): determines which
      agent/human is responsible for a flow state mutation; uses a precedence
      chain of explicit → flow → worktree.
    - **Display / PR body** (normalize_actor): normalises stored actor strings
      for human-readable rendering; maps legacy aliases, filters placeholders.
    """

    @staticmethod
    def _normalize(actor: str | None) -> str | None:
        """Internal normalizer for flow-operation comparisons."""
        if actor is None:
            return None
        value = actor.strip()
        if not value:
            return None
        if value.lower() in AI_ASSISTANT_ACTORS:
            return "ai-assistant"
        return value

    @classmethod
    def _is_placeholder(cls, actor: str | None) -> bool:
        """Return True if actor conveys no meaningful identity (flow layer)."""
        if actor is None:
            return True
        norm = cls._normalize(actor)
        if norm is None:
            return True
        return norm.lower() in _PLACEHOLDER_ACTORS

    @classmethod
    def normalize_actor(cls, actor: str | None) -> str | None:
        """Normalize an actor identifier for display (PR body, UI).

        Handles:
        - ``None`` / empty / whitespace-only → ``None``
        - Placeholder values (unknown, system, workflow, ai-assistant, …) → ``None``
        - Actor aliases (``Agent-Claude``) → standard backend (``claude``)
        - Already-standard format (``claude/sonnet-4.6``) → pass through, trimmed

        This is the single source of truth for actor normalisation at the
        display / PR-body layer.  Use ``resolve_actor`` / ``resolve_for_branch``
        for flow-state mutations.

        Delegates to utils.actor_utils.normalize_actor for implementation.
        """
        return _normalize_actor_for_display(actor)

    @classmethod
    def get_worktree_actor(cls) -> str:
        """Get git user.name from current worktree as the final source of truth."""
        try:
            name = GitClient().get_config("user.name")
            if name and not cls._is_placeholder(name):
                return name
        except Exception:
            pass
        return "human"

    @classmethod
    def resolve_actor(
        cls,
        explicit_actor: str | None = None,
        flow_actor: str | None = None,
    ) -> str:
        """Resolve actor for a flow-state mutation.

        Precedence (Single Source of Truth):
        1. Explicit actor (CLI ``--actor`` argument)
        2. Flow actor (``latest_actor`` from storage)
        3. Worktree actor (git config ``user.name``)
        """
        explicit = cls._normalize(explicit_actor)
        flow = cls._normalize(flow_actor)

        if explicit is not None and not cls._is_placeholder(explicit):
            return explicit
        if flow is not None and not cls._is_placeholder(flow):
            return flow
        return cls.get_worktree_actor()

    @classmethod
    def resolve_for_branch(
        cls,
        store: Any,
        branch: str,
        explicit_actor: str | None = None,
    ) -> str:
        """Resolve actor with branch flow context."""
        flow_data_raw = store.get_flow_state(branch)
        flow_data = flow_data_raw if isinstance(flow_data_raw, dict) else {}
        flow_actor = flow_data.get("latest_actor")
        return cls.resolve_actor(explicit_actor, flow_actor)

    @classmethod
    def resolve_initiator(cls, branch: str) -> str:
        """Resolve the primary initiator for a new flow.

        Logic:
        1. If branch follows orchestra managed pattern (task/issue-N)
           -> orchestra:manager
        2. Else -> manual
        """
        if branch.startswith("task/issue-"):
            return ORCHESTRA_MANAGER
        return MANUAL_INITIATOR
