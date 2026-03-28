"""Unified actor/signature resolution for workflow and flow events."""

from typing import Any

WORKFLOW_ACTOR = "workflow"
AI_ASSISTANT_ACTORS = {"ai-assistant", "ai_assistant"}
_PLACEHOLDER_ACTORS = {"", "unknown", "server", "system"}


class SignatureService:
    """Resolve effective actor using explicit -> flow -> workflow precedence."""

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

    @staticmethod
    def _is_placeholder(actor: str | None) -> bool:
        if actor is None:
            return True
        return actor.strip().lower() in _PLACEHOLDER_ACTORS

    @classmethod
    def resolve_actor(
        cls,
        explicit_actor: str | None = None,
        flow_actor: str | None = None,
        workflow_actor: str = WORKFLOW_ACTOR,
    ) -> str:
        """Resolve actor.

        Rules:
        - ai-assistant is preserved as-is (special actor).
        - explicit actor wins if it's non-placeholder.
        - else use flow actor when available.
        - else fallback to workflow actor.
        """
        explicit = cls._normalize(explicit_actor)
        flow = cls._normalize(flow_actor)

        if cls.is_ai_assistant(explicit):
            return "ai-assistant"
        if explicit is not None and not cls._is_placeholder(explicit):
            return explicit
        if flow is not None and not cls._is_placeholder(flow):
            return flow
        return workflow_actor

    @classmethod
    def resolve_for_branch(
        cls,
        store: Any,
        branch: str,
        explicit_actor: str | None = None,
        workflow_actor: str = WORKFLOW_ACTOR,
    ) -> str:
        """Resolve actor with branch flow context."""
        flow_data_raw = store.get_flow_state(branch)
        flow_data = flow_data_raw if isinstance(flow_data_raw, dict) else {}
        flow_actor = flow_data.get("latest_actor")
        return cls.resolve_actor(explicit_actor, flow_actor, workflow_actor)
