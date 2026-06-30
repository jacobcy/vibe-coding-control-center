"""Protocol definitions for PR cache access.

Isolates status aggregation (services/shared/status_pipeline.py) from the
concrete PRService implementation to respect the services/ boundary
(shared/ must not import from pr/).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vibe3.models import PRResponse


class PRCachePort(Protocol):
    """Read-only port for refreshing the recent-PR cache.

    Implemented by services/pr.service.PRService; consumed by status aggregation
    so the shared layer never depends on the pr subpackage.
    """

    def refresh_recent_pr_cache(
        self,
        *,
        force: bool = False,
        limit: int = 50,
        max_age_minutes: int = 10,
        sync_context_cache: bool = True,
    ) -> dict[str, PRResponse]:
        """Refresh recent PR cache if stale and return branch -> PR mapping."""
        ...
