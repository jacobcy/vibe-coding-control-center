"""Timeline event parsing from GitHub comments."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from vibe3.models.flow import TimelineEvent


def parse_timeline_from_comments(
    comments: list[dict[str, Any]],
) -> list[TimelineEvent]:
    """Parse timeline events from GitHub issue comments.

    Args:
        comments: List of GitHub comment objects with author, body, created_at

    Returns:
        List of TimelineEvent objects extracted from automation markers
    """
    events: list[TimelineEvent] = []

    # Pattern to match automation markers: ### event_type
    marker_pattern = re.compile(r"^###\s+(\w+)", re.MULTILINE)

    for comment in comments:
        if not isinstance(comment, dict):
            continue

        body = str(comment.get("body") or "")
        author = comment.get("author") or {}
        actor = str(author.get("login") or "unknown")
        created_at_str = str(comment.get("created_at") or "")

        # Find all automation markers in this comment
        for match in marker_pattern.finditer(body):
            event_type = match.group(1)

            # Extract detail (text after the marker)
            start = match.end()
            detail = body[start:].strip().split("\n\n")[0].strip()

            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                timestamp = datetime.now()

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
