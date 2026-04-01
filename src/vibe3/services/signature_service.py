"""Unified actor/signature resolution for workflow and flow events."""

from typing import Any

from vibe3.clients.git_client import GitClient

WORKFLOW_ACTOR = "workflow"
AI_ASSISTANT_ACTORS = {"ai-assistant", "ai_assistant"}
_PLACEHOLDER_ACTORS = {"", "unknown", "server", "system", "workflow"}


class SignatureService:
    """Resolve effective actor using explicit -> flow -> worktree precedence."""

    @staticmethod
    def is_ai_assistant(actor: str | None) -> bool:
        if actor is None:
            return False
        return actor.strip().lower() in AI_ASSISTANT_ACTORS

    @staticmethod
    def _normalize(actor: str | None) -> str | None:
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
        if actor is None:
            return True
        norm = cls._normalize(actor)
        if norm is None:
            return True
        return norm.lower() in _PLACEHOLDER_ACTORS

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
        """Resolve actor.

        Precedence (Single Source of Truth):
        1. Explicit actor (CLI command argument)
        2. Flow actor (latest_actor from storage)
        3. Worktree actor (git config user.name)
        """
        explicit = cls._normalize(explicit_actor)
        flow = cls._normalize(flow_actor)

        # 1. Command explicit wins if non-placeholder
        if explicit is not None and not cls._is_placeholder(explicit):
            return explicit

        # 2. Flow actor wins if available and non-placeholder
        if flow is not None and not cls._is_placeholder(flow):
            return flow

        # 3. Fallback to worktree identity (never None)
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
