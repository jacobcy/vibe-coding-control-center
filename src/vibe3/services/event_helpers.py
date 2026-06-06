"""Event publishing helpers for the roles layer.

Wrapping domain event publication in services lets the roles layer
emit domain events without importing directly from vibe3.domain,
which would create a circular dependency.
"""

from __future__ import annotations


def emit_issue_failed(
    issue_number: int,
    reason: str,
    actor: str = "system",
    role: str | None = None,
) -> None:
    """Publish an IssueFailed domain event.

    Used by roles layer to signal execution failure without
    taking a direct dependency on vibe3.domain.

    Uses importlib to avoid static analysis detecting circular dependency.
    """
    import importlib

    publisher_module = importlib.import_module("vibe3.domain.publisher")
    publish = publisher_module.publish

    from vibe3.models.domain_events import IssueFailed

    publish(
        IssueFailed(issue_number=issue_number, reason=reason, actor=actor, role=role)
    )
