"""External event recording service for handoff system."""

from typing import Any, Callable

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.flow import FlowEvent
from vibe3.services.handoff_storage import HandoffStorage


class ExternalEventRecorder:
    """Records external events (CI status, PR comments) as handoff events."""

    def __init__(
        self,
        store: SQLiteClient,
        storage: HandoffStorage,
        get_handoff_events_func: Callable[
            [str, str | None, int | None], list[FlowEvent]
        ],
    ) -> None:
        self.store = store
        self.storage = storage
        self._get_handoff_events = get_handoff_events_func

    def get_handoff_events(
        self,
        branch: str,
        event_type_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[FlowEvent]:
        """Query handoff events using injected function."""
        return self._get_handoff_events(branch, event_type_prefix, limit)

    def record_ci_status(
        self,
        branch: str,
        pr_number: int,
        status: str,
        actor: str = "system/github",
    ) -> bool:
        """Record CI status as external event.

        Only records if status changed from last recorded status.

        Args:
            branch: Branch name
            pr_number: PR number
            status: CI status string (e.g., "SUCCESS", "FAILURE", "PENDING")
            actor: Actor string (defaults to "system/github")

        Returns:
            True if event was recorded, False if skipped (no change)
        """
        # Query last recorded CI status for this branch
        last_events = self.get_handoff_events(
            branch, event_type_prefix="handoff_ci_status", limit=1
        )

        # Check if status changed
        if last_events and last_events[0].refs:
            last_status = last_events[0].refs.get("status")
            if last_status == status:
                logger.bind(
                    domain="handoff",
                    action="record_ci_status",
                    branch=branch,
                    pr_number=pr_number,
                    status=status,
                ).debug("CI status unchanged, skipping recording")
                return False

        # Record new status
        detail = f"PR #{pr_number} CI status: {status}"
        refs = {
            "pr_number": str(pr_number),
            "status": status,
        }

        self.store.add_event(
            branch,
            "handoff_ci_status",
            actor,
            detail=detail,
            refs=refs,
        )

        logger.bind(
            domain="handoff",
            action="record_ci_status",
            branch=branch,
            pr_number=pr_number,
            status=status,
        ).info("Recorded CI status change")
        return True

    def record_pr_comments(
        self,
        branch: str,
        pr_number: int,
        comments: list[dict[str, Any]],
        review_comments: list[dict[str, Any]] | None = None,
        actor: str = "system/github",
    ) -> int:
        """Record PR comments as external events.

        Only records comments not already recorded (dedup by comment ID).

        Args:
            branch: Branch name
            pr_number: PR number
            comments: List of general comments (each has 'id' or 'number' field)
            review_comments: List of review comments (each has 'id' field)
            actor: Actor string (defaults to "system/github")

        Returns:
            Number of new comments recorded
        """
        if review_comments is None:
            review_comments = []

        # Query existing recorded comment IDs
        existing_events = self.get_handoff_events(
            branch, event_type_prefix="handoff_pr_comment"
        )
        recorded_ids = set()
        for event in existing_events:
            if event.refs:
                comment_id = event.refs.get("comment_id")
                if comment_id:
                    recorded_ids.add(str(comment_id))

        # Record new comments
        recorded_count = 0
        all_comments = []

        # Process general comments (use 'id' or 'number' field)
        for comment in comments:
            comment_id = str(comment.get("id") or comment.get("number"))
            if comment_id and comment_id not in recorded_ids:
                all_comments.append(("general", comment_id, comment))

        # Process review comments (use 'id' field)
        for comment in review_comments:
            comment_id = str(comment.get("id"))
            if comment_id and comment_id not in recorded_ids:
                all_comments.append(("review", comment_id, comment))

        # Record each new comment
        for comment_type, comment_id, comment_data in all_comments:
            author = comment_data.get("author", {})
            author_login = (
                author.get("login", "unknown")
                if isinstance(author, dict)
                else str(author)
            )
            body = comment_data.get("body", "")
            created_at = comment_data.get("createdAt") or comment_data.get(
                "created_at", ""
            )

            # Truncate body for event detail (max 200 chars)
            truncated_body = body[:200] if len(body) > 200 else body

            detail = (
                f"PR #{pr_number} {comment_type} comment by "
                f"{author_login}: {truncated_body}"
            )
            refs = {
                "pr_number": str(pr_number),
                "comment_id": comment_id,
                "comment_type": comment_type,
                "author": author_login,
                "created_at": created_at,
            }

            self.store.add_event(
                branch,
                "handoff_pr_comment",
                actor,
                detail=detail,
                refs=refs,
            )
            recorded_count += 1

        if recorded_count > 0:
            logger.bind(
                domain="handoff",
                action="record_pr_comments",
                branch=branch,
                pr_number=pr_number,
                count=recorded_count,
            ).info(f"Recorded {recorded_count} new PR comments")

        return recorded_count
