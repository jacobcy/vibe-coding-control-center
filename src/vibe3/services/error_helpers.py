"""Backward compatibility — migrated to services.shared.errors."""

from vibe3.services.shared.errors import (  # noqa: F401
    has_recent_specific_error,
    record_dispatch_failure_if_unexpected,
    record_error,
)
