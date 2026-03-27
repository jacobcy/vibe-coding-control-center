"""Flow query mixin for FlowService."""

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.flow import FlowEvent, FlowState

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.sqlite_client import SQLiteClient


class FlowQueryMixin:
    """Mixin for flow query operations."""

    store: "SQLiteClient"
    git_client: "GitClient"

    def get_handoff_events(
        self, branch: str, event_type_prefix: str = "handoff_", limit: int | None = None
    ) -> list[FlowEvent]:
        """Get handoff events for branch.

        Args:
            branch: Branch name
            event_type_prefix: Event type filter prefix
            limit: Maximum number of events

        Returns:
            List of FlowEvent objects
        """
        events_data = self.store.get_events(
            branch, event_type_prefix=event_type_prefix, limit=limit
        )
        return [FlowEvent(**e) for e in events_data]

    def get_flow_state(self, branch: str) -> FlowState | None:
        """Get flow state for branch.

        Args:
            branch: Branch name

        Returns:
            FlowState or None if not found
        """
        state_data = self.store.get_flow_state(branch)
        if not state_data:
            return None
        return FlowState(**state_data)

    def get_git_common_dir(self) -> str:
        """Get git common directory path.

        Returns:
            Path to git common directory
        """
        return self.git_client.get_git_common_dir()

    def bind_spec(
        self,
        branch: str,
        spec_ref: str,
        actor: str = "system",
    ) -> None:
        """Bind a spec to a flow.

        Args:
            branch: Branch name
            spec_ref: Spec file reference
            actor: Actor performing the bind
        """
        self.store.update_flow_state(branch, spec_ref=spec_ref, latest_actor=actor)
        self.store.add_event(
            branch, "spec_bound", actor, detail=f"Spec bound: {spec_ref}"
        )
        logger.bind(branch=branch, spec=spec_ref).info("Spec bound to flow")
