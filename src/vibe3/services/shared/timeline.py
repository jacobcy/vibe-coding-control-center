"""Timeline event parsing from GitHub comments."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from vibe3.models import TimelineEvent
from vibe3.services.flow.timeline import TIMELINE_DISPLAY_MAP


def parse_timeline_from_comments(
    comments: list[dict[str, Any]],
) -> list[TimelineEvent]:
    """Parse timeline events from GitHub issue comments.

    Args:
        comments: List of GitHub comment objects with author, body, createdAt

    Returns:
        List of TimelineEvent objects extracted from [flow] markers
    """
    events: list[TimelineEvent] = []

    # Reverse map: display text -> event_type
    reverse_map = {v: k for k, v in TIMELINE_DISPLAY_MAP.items()}

    # Pattern to match [flow] display_text
    marker_pattern = re.compile(r"^\[flow\]\s+([^\n]+)", re.MULTILINE)

    for comment in comments:
        if not isinstance(comment, dict):
            continue

        body = str(comment.get("body") or "")
        author = comment.get("author") or {}
        actor = str(author.get("login") or "unknown")

        # GitHub API uses camelCase: createdAt
        created_at_str = str(
            comment.get("createdAt") or comment.get("created_at") or ""
        )

        # Find all [flow] markers in this comment
        for match in marker_pattern.finditer(body):
            display_text = match.group(1).strip()

            # Map display text back to event_type
            event_type = reverse_map.get(
                display_text, display_text.lower().replace(" ", "_")
            )

            # Extract detail (text after the marker)
            start = match.end()
            detail = body[start:].strip().split("\n\n")[0].strip()

            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                # Use deterministic sentinel instead of datetime.now()
                timestamp = datetime.min

            events.append(
                TimelineEvent(
                    timestamp=timestamp.isoformat(),
                    event_type=event_type,
                    actor=actor,
                    detail=detail,
                )
            )

    # Sort by timestamp
    events.sort(key=lambda e: e.timestamp)
    return events
