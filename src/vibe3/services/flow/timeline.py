"""Flow timeline event and comment coordination service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.config import TimelineCommentPolicy


from vibe3.services.shared.timeline import TIMELINE_DISPLAY_MAP


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
        from vibe3.clients import GitHubClient, SQLiteClient

        self.store = SQLiteClient() if store is None else store
        self.github_client = GitHubClient() if github_client is None else github_client

    def record_timeline_event(
        self,
        branch: str,
        event_type: str,
        actor: str,
        detail: str = "",
        issue_number: int | None = None,
        repo: str | None = None,
        policy: TimelineCommentPolicy | None = None,
    ) -> None:
        """Record timeline event with configurable comment policy.

        Args:
            branch: Flow branch
            event_type: Event type (flow_blocked, flow_failed, resumed, etc.)
            actor: Actor performing the action
            detail: Event detail/reason
            issue_number: GitHub issue number (optional)
            repo: Repository (owner/repo format, optional)
            policy: Comment policy configuration (default: DEFAULT_COMMENT_POLICY)
        """
        # Always record event in SQLite
        self.store.add_event(branch, event_type, actor, detail)

        # Use default policy if not provided
        if policy is None:
            from vibe3.config import DEFAULT_COMMENT_POLICY

            policy = DEFAULT_COMMENT_POLICY

        # Check policy - should this event write comment?
        if not policy.should_write_comment(event_type):
            logger.bind(
                domain="flow",
                action="timeline",
                branch=branch,
                event_type=event_type,
            ).debug("Timeline event recorded (SQLite only, policy=no_comment)")
            return

        # Skip if no issue_number (required for comment)
        if issue_number is None:
            logger.bind(
                domain="flow",
                action="timeline",
                branch=branch,
                event_type=event_type,
            ).debug("Timeline event recorded (SQLite only, no issue_number)")
            return

        # Check dedupe: skip if latest timeline comment has same event_type
        if self._should_skip_duplicate_comment(issue_number, event_type):
            logger.bind(
                domain="flow",
                action="timeline",
                issue_number=issue_number,
                event_type=event_type,
            ).info("Timeline comment skipped (duplicate event_type)")
            return

        # Build and write comment (only for events allowed by policy)
        comment_body = self._build_timeline_comment(event_type, detail)

        try:
            self.github_client.add_comment(issue_number, comment_body, repo=repo)
            logger.bind(
                domain="flow",
                action="timeline",
                issue_number=issue_number,
                event_type=event_type,
            ).success("Timeline comment added (policy=allowed)")
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
        display_text = TIMELINE_DISPLAY_MAP.get(
            event_type, event_type.replace("_", " ").title()
        )

        return f"[flow] {display_text}\n\n{detail}"

    def _should_skip_duplicate_comment(
        self, issue_number: int, event_type: str
    ) -> bool:
        """Check if latest timeline comment has same event_type.

        Args:
            issue_number: GitHub issue number
            event_type: New event type

        Returns:
            True if duplicate (should skip), False otherwise
        """
        import re

        try:
            issue_payload = self.github_client.view_issue(
                issue_number, fields=["comments"]
            )
            if not isinstance(issue_payload, dict):
                return False

            comments = issue_payload.get("comments")
            if not isinstance(comments, list) or not comments:
                return False

            # Get latest comment
            latest_comment = comments[-1]
            if not isinstance(latest_comment, dict):
                return False

            body = str(latest_comment.get("body") or "")

            # Check if latest comment has [flow] marker
            if not body.startswith("[flow]"):
                return False

            # Reverse map: display text -> event_type
            reverse_map = {v: k for k, v in TIMELINE_DISPLAY_MAP.items()}

            # Extract display text from comment
            # Pattern: "[flow] {display_text}"
            pattern = r"^\[flow\]\s+([^\n]+)"
            match = re.match(pattern, body)
            if not match:
                return False

            display_text = match.group(1).strip()

            # Map display text back to event_type
            latest_event_type = reverse_map.get(display_text)
            if not latest_event_type:
                return False

            # Skip if same event_type
            return latest_event_type == event_type

        except Exception as e:
            logger.bind(
                domain="flow",
                action="timeline_dedupe",
                issue_number=issue_number,
                error=str(e),
            ).warning("Dedupe check failed, proceeding with comment")
            return False
