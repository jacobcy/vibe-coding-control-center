"""Backward compatibility — migrated to services.shared.labels."""

from vibe3.services.shared.labels import (  # noqa: F401
    clean_old_state_labels,
    has_manager_assignee,
    normalize_assignees,
    normalize_labels,
    should_skip_from_queue,
)
