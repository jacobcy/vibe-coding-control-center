"""Unified blocked state management service.

This service provides a single entry point for managing blocked state across
three data sources: database, issue body, and issue labels.

Design Principles:
1. Issue body + labels = Authoritative truth (remote-first)
2. Database = Performance cache (local optimization)
3. Qualify gate = Cache synchronizer (ensures coherence)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.services.blocked_state_io import BlockedStateIO
from vibe3.services.blocked_state_types import BlockedState, ConsistencyReport
from vibe3.services.flow_timeline_service import FlowTimelineService
from vibe3.services.label_service import LabelService

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient


class BlockedStateService:
    """Single entry point for blocked state management.

    Coordinates writes across three sources:
    1. Issue body (truth) - critical, must succeed
    2. Database (cache) - non-critical, can be stale
    3. Labels (signal) - non-critical, can be stale
    """

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        label_service: LabelService | None = None,
        store: SQLiteClient | None = None,
    ) -> None:
        self._io = BlockedStateIO(
            github_client=github_client or GitHubClient(),
            label_service=label_service,
            store=store,
        )
        self.store = store

    # ========================================================================
    # Public API: Write Operations
    # ========================================================================

    def block(
        self,
        branch: str,
        reason: str | None,
        blocked_by_issue: int | None = None,
        actor: str = "system",
        issue_number: int | None = None,
        event_type: str = "flow_blocked",
    ) -> None:
        """Atomically set blocked state in all three sources."""
        if issue_number:
            try:
                self._io.write_body_projection(
                    issue_number=issue_number,
                    reason=reason,
                    blocked_by_issue=blocked_by_issue,
                )
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="block",
                    branch=branch,
                ).error(f"Failed to write issue body projection: {exc}")
                raise

        if self.store:
            try:
                self._io.write_database_cache(
                    branch=branch,
                    reason=reason,
                    blocked_by_issue=blocked_by_issue,
                    actor=actor,
                )
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="block",
                    branch=branch,
                ).warning(f"Failed to write database cache: {exc}")

        if issue_number:
            try:
                self._io.write_label_state(
                    issue_number=issue_number,
                    target_state=IssueState.BLOCKED,
                    actor=actor,
                )
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="block",
                    branch=branch,
                ).warning(f"Failed to write label state: {exc}")

        if self.store and issue_number:
            try:
                timeline = FlowTimelineService(store=self.store)
                timeline.record_timeline_event(
                    branch=branch,
                    event_type=event_type,
                    actor=actor,
                    detail=reason or "",
                    issue_number=issue_number,
                )
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="block",
                    branch=branch,
                ).warning(f"Failed to write timeline event: {exc}")

    def unblock(
        self,
        branch: str,
        target_state: IssueState,
        actor: str = "human:resume",
        issue_number: int | None = None,
    ) -> None:
        """Atomically clear blocked state in all three sources."""
        if issue_number:
            try:
                self._io.clear_body_projection(issue_number=issue_number)
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="unblock",
                    branch=branch,
                ).error(f"Failed to clear issue body projection: {exc}")
                raise

        if self.store:
            try:
                self._io.clear_database_cache(branch=branch, actor=actor)
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="unblock",
                    branch=branch,
                ).warning(f"Failed to clear database cache: {exc}")

        if issue_number:
            try:
                self._io.write_label_state(
                    issue_number=issue_number,
                    target_state=target_state,
                    actor=actor,
                )
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="unblock",
                    branch=branch,
                ).warning(f"Failed to write label state: {exc}")

        if self.store and issue_number:
            try:
                timeline = FlowTimelineService(store=self.store)
                timeline.record_timeline_event(
                    branch=branch,
                    event_type="resumed",
                    actor=actor,
                    detail=f"Resumed to {target_state.value}",
                    issue_number=issue_number,
                )
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="unblock",
                    branch=branch,
                ).warning(f"Failed to write timeline event: {exc}")

    # ========================================================================
    # Public API: Query Operations
    # ========================================================================

    def is_blocked(
        self,
        branch: str,
        issue_number: int,
    ) -> bool:
        """Check if flow is blocked (reads from authoritative truth)."""
        state = self.resolve_truth(branch, issue_number)
        return state.is_blocked

    def get_blocked_reason(
        self,
        branch: str,
        issue_number: int,
    ) -> str | None:
        """Get blocked reason from authoritative truth."""
        state = self.resolve_truth(branch, issue_number)
        return state.blocked_reason

    def write_cache(
        self,
        branch: str,
        reason: str | None,
        blocked_by_issue: int | None,
        actor: str = "system",
    ) -> None:
        """Write blocked state to database cache only (no body/label update).

        Use when you need to update the cache without touching the truth source.
        For example, qualify gate uses this to align cache to truth.
        """
        self._io.write_database_cache(
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
            actor=actor,
        )

    # ========================================================================
    # Public API: Synchronization
    # ========================================================================

    def sync_cache_from_truth(
        self,
        branch: str,
        issue_number: int,
    ) -> BlockedState:
        """Synchronize local cache (DB) from authoritative truth (body)."""
        truth_state = self._io.read_body_projection(issue_number)

        cache_state = self._io.read_database_cache(branch) if self.store else None

        needs_sync = (
            not cache_state
            or truth_state.is_blocked != cache_state.is_blocked
            or truth_state.blocked_reason != cache_state.blocked_reason
            or truth_state.blocked_by != cache_state.blocked_by
        )

        if needs_sync:
            logger.bind(
                domain="blocked_state",
                action="sync_cache",
                branch=branch,
                truth_blocked=truth_state.is_blocked,
                cache_blocked=cache_state.is_blocked if cache_state else None,
            ).info("Syncing database cache from issue body truth")

            if truth_state.is_blocked:
                self._io.write_database_cache(
                    branch=branch,
                    reason=truth_state.blocked_reason,
                    blocked_by_issue=(
                        truth_state.blocked_by[0] if truth_state.blocked_by else None
                    ),
                    actor="system:sync",
                )
            else:
                self._io.clear_database_cache(branch=branch, actor="system:sync")

        return truth_state

    def resolve_truth(
        self,
        branch: str,
        issue_number: int,
    ) -> BlockedState:
        """Resolve authoritative truth with fallback to database."""
        body_state = self._io.read_body_projection(issue_number)

        if body_state.is_blocked:
            return body_state

        if self.store:
            db_state = self._io.read_database_cache(branch)
            if db_state.is_blocked:
                return db_state

        return body_state

    def validate_consistency(
        self,
        branch: str,
        issue_number: int,
    ) -> ConsistencyReport:
        """Validate consistency across all three sources."""
        return ConsistencyReport(
            database_state=self._io.read_database_cache(branch),
            body_state=self._io.read_body_projection(issue_number),
            label_state=self._io.read_label_state(issue_number),
        )
