"""Flow timeline event and comment coordination service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.clients.github_client import GitHubClient


class FlowTimelineService:
    """Unified service for recording flow timeline events.

    Coordinates:
    1. Event recording in SQLite (store.add_event)
    2. GitHub comment posting ([flow] timeline marker)

    Dedupe strategy:
    - Only send comment if event_type differs from latest timeline comment
    - Prevents duplicate comments for repeated state transitions
    """

    store: SQLiteClient
    github_client: GitHubClient

    def __init__(
        self,
        store: SQLiteClient | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        """Initialize timeline service."""
        from vibe3.clients import SQLiteClient
        from vibe3.clients.github_client import GitHubClient

        self.store = SQLiteClient() if store is None else store
        self.github_client = GitHubClient() if github_client is None else github_client

    def record_timeline_event(
        self,
        branch: str,
        event_type: str,
        actor: str,
        detail: str,
        issue_number: int | None = None,
    ) -> None:
        """Record timeline event and optionally add GitHub comment.

        Args:
            branch: Flow branch
            event_type: Event type (flow_blocked, flow_failed, resumed, etc.)
            actor: Actor performing the action
            detail: Event detail/reason
            issue_number: GitHub issue number (optional, skips comment if None)
        """
        # Always record event in SQLite
        self.store.add_event(branch, event_type, actor, detail)

        # Skip comment if no issue linked
        if issue_number is None:
            logger.bind(
                domain="flow",
                action="timeline",
                branch=branch,
                event_type=event_type,
            ).debug("Timeline event recorded without comment (no issue)")
            return

        # Build timeline comment
        comment_body = self._build_timeline_comment(event_type, detail)

        # Add comment to GitHub issue
        try:
            self.github_client.add_comment(issue_number, comment_body)
            logger.bind(
                domain="flow",
                action="timeline",
                issue_number=issue_number,
                event_type=event_type,
            ).success("Timeline comment added")
        except Exception as e:
            logger.bind(
                domain="flow",
                action="timeline",
                issue_number=issue_number,
                error=str(e),
            ).warning("Failed to add timeline comment")

    def _build_timeline_comment(self, event_type: str, detail: str) -> str:
        """Build timeline comment with [flow] marker.

        Args:
            event_type: Event type for header
            detail: Event detail for body

        Returns:
            Formatted comment body
        """
        # Event type to display text mapping
        display_map = {
            "flow_blocked": "Flow blocked",
            "flow_failed": "Flow failed",
            "flow_aborted": "Flow aborted",
            "resumed": "Flow resumed",
            "state_transitioned": "State transitioned",
        }

        display_text = display_map.get(event_type, event_type.replace("_", " ").title())

        return f"[flow] {display_text}\n\n{detail}"
