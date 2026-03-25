"""Handoff usecase service - orchestrates handoff operations.

This service handles the orchestration of handoff operations:
- Reference recording
- Artifact writing
- Event appending
- Error handling
"""

from pathlib import Path

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.services.handoff_event_service import (
    create_handoff_artifact,
    persist_handoff_event,
)
from vibe3.services.handoff_service import HandoffService


class HandoffUseCase:
    """Orchestrates handoff operations.

    This service coordinates between:
    - HandoffService (reference management)
    - HandoffEventService (artifact and event persistence)
    - GitClient (branch context)
    """

    def __init__(
        self,
        git_client: GitClient | None = None,
        handoff_service: HandoffService | None = None,
    ):
        """Initialize with dependencies.

        Args:
            git_client: Git client for branch context
            handoff_service: Handoff service for reference management
        """
        self.git_client = git_client or GitClient()
        self.handoff_service = handoff_service or HandoffService()

    def record_reference(
        self,
        ref_type: str,
        ref_value: str,
        actor: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
    ) -> None:
        """Record a handoff reference.

        Args:
            ref_type: Type of reference (plan, report, audit)
            ref_value: Reference value (file path, etc.)
            actor: Actor who created the reference
            next_step: Optional next step
            blocked_by: Optional blocker
        """
        try:
            # Map ref_type to service method
            method_map = {
                "plan": self.handoff_service.record_plan,
                "report": self.handoff_service.record_report,
                "audit": self.handoff_service.record_audit,
            }

            method = method_map.get(ref_type)
            if not method:
                logger.warning(f"Unknown reference type: {ref_type}")
                return

            method(ref_value, next_step, blocked_by, actor)
            logger.info(f"Recorded {ref_type} reference", ref=ref_value, actor=actor)

        except Exception as exc:
            logger.error(f"Failed to record reference: {exc}")
            raise

    def create_artifact(self, prefix: str, content: str) -> tuple[str, Path] | None:
        """Create a handoff artifact.

        Args:
            prefix: Artifact prefix (e.g., "plan", "run")
            content: Artifact content

        Returns:
            Tuple of (branch, artifact_path) or None on failure
        """
        try:
            result = create_handoff_artifact(prefix, content)
            return result
        except Exception as exc:
            logger.error(f"Failed to create artifact: {exc}")
            return None

    def append_event(
        self,
        event_type: str,
        actor: str,
        detail: str,
        refs: dict[str, str] | None = None,
        flow_state_updates: dict[str, object] | None = None,
    ) -> None:
        """Append a handoff event.

        Args:
            event_type: Type of event (e.g., "handoff_plan", "handoff_run")
            actor: Actor who triggered the event
            detail: Event detail
            refs: Optional references
            flow_state_updates: Optional flow state updates
        """
        try:
            branch = self.git_client.get_current_branch()

            persist_handoff_event(
                branch=branch,
                event_type=event_type,
                actor=actor,
                detail=detail,
                refs=refs or {},
                flow_state_updates=flow_state_updates,
            )

            logger.info(
                "Appended event",
                event_type=event_type,
                branch=branch,
                actor=actor,
            )

        except Exception as exc:
            logger.error(f"Failed to append event: {exc}")
