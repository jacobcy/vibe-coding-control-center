"""Event publishing helpers for the roles layer.

Wrapping domain event publication in services lets the roles layer
emit domain events without importing directly from vibe3.domain,
which would create a circular dependency.
"""

from __future__ import annotations

from vibe3.models import IssueFailed, publish


def emit_issue_failed(
    issue_number: int,
    reason: str,
    actor: str = "system",
    role: str | None = None,
) -> None:
    """Publish an IssueFailed domain event."""
    publish(
        IssueFailed(issue_number=issue_number, reason=reason, actor=actor, role=role)
    )
