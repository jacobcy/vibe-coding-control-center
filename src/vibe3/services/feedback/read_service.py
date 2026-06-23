"""Feedback read service: query and display observations."""

from __future__ import annotations

from typing import Any

from vibe3.clients.feedback_store import FeedbackStore


class FeedbackReadService:
    """Service for querying feedback observations."""

    def __init__(self, store: FeedbackStore | None = None) -> None:
        """Initialize with optional store dependency.

        Args:
            store: FeedbackStore instance. If None, creates a new one.
        """
        self.store = store or FeedbackStore()

    def list_observations(
        self,
        source: str | None = None,
        symptom: str | None = None,
        failure_mode: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List observations with optional filters.

        Args:
            source: Filter by source_material (exact match)
            symptom: Filter by symptom (substring match)
            failure_mode: Filter by observed_failure_mode (exact match)
            limit: Max results to return

        Returns:
            List of observation dicts
        """
        return self.store.list_observations(
            source=source,
            symptom=symptom,
            failure_mode=failure_mode,
            limit=limit,
        )

    def show_observation(self, observation_id: str) -> dict[str, Any] | None:
        """Get full observation details by ID.

        Args:
            observation_id: Unique observation identifier

        Returns:
            Full observation dict, or None if not found
        """
        return self.store.get_by_id(observation_id)

    def get_stats(self, group_by: str = "failure_mode") -> dict[str, int]:
        """Get aggregated statistics.

        Args:
            group_by: Field to group by ('failure_mode' or 'cluster_key')

        Returns:
            Dict mapping group value to count
        """
        return self.store.get_stats(group_by=group_by)
