"""Coordination resolver for remote-first blocked/dependency reads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.coordination_truth import CoordinationTruth
from vibe3.models.data_source import DataSource
from vibe3.observability.degraded_mode import (
    DegradedModeReason,
    get_degraded_manager,
)
from vibe3.services.flow_status_resolver import FlowStatusResolver

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient


class CoordinationResolver:
    """Resolver for remote-first coordination state.

    Implements truth table:
    - Collaboration fields (blocked/dependencies): remote-first
    - Execution fields (worktree/actor): local-only
    """

    def __init__(
        self,
        store: SQLiteClient,
        flow_status_resolver: FlowStatusResolver | None = None,
    ) -> None:
        """Initialize resolver.

        Args:
            store: SQLiteClient for database operations
            flow_status_resolver: Optional FlowStatusResolver (defaults to creating one)
        """
        self.store = store
        self.flow_status_resolver = flow_status_resolver or FlowStatusResolver(
            store=store
        )

    def resolve_coordination(
        self,
        branch: str,
        issue_number: int | None = None,
    ) -> CoordinationTruth:
        """Resolve coordination truth with remote-first strategy.

        Args:
            branch: Branch name to query
            issue_number: Task issue number (required for remote reads)

        Returns:
            CoordinationTruth with collaboration fields from remote,
            execution fields from local
        """
        # Step 1: Try remote read for collaboration fields
        blocked_reason_remote = None
        blocked_by_issue_remote = None
        dependencies_remote = []

        if issue_number:
            try:
                remote_truth = self._read_remote_collaboration(branch, issue_number)
                if remote_truth:
                    blocked_reason_remote = remote_truth.get("blocked_reason")
                    blocked_by_issue_remote = remote_truth.get("blocked_by_issue")
                    dependencies_remote = remote_truth.get("dependencies", [])
            except Exception as e:
                # GitHub API failure → enter degraded mode
                degraded = get_degraded_manager()
                degraded.enter_degraded_mode(DegradedModeReason.GITHUB_API_ERROR)
                logger.bind(
                    domain="resolver",
                    action="resolve_coordination",
                    error=str(e),
                ).warning("Remote read failed, falling back to local DB")

        # Step 2: Read local DB for all fields (fallback + execution fields)
        flow_state = self.store.get_flow_state(branch)

        # Step 3: Merge with truth table (remote > local for collaboration)
        truth = CoordinationTruth(
            # Collaboration: remote-first, fallback to local
            blocked_reason=blocked_reason_remote
            or (flow_state.get("blocked_reason") if flow_state else None),
            blocked_reason_source=(
                DataSource.ISSUE_BODY_FALLBACK
                if blocked_reason_remote
                else DataSource.LOCAL_SQLITE if flow_state else None
            ),
            blocked_by_issue=blocked_by_issue_remote
            or (flow_state.get("blocked_by_issue") if flow_state else None),
            blocked_by_issue_source=(
                DataSource.ISSUE_BODY_FALLBACK
                if blocked_by_issue_remote
                else DataSource.LOCAL_SQLITE if flow_state else None
            ),
            dependencies=dependencies_remote
            or (self.store.get_dependency_links(branch)),
            dependencies_source=(
                DataSource.ISSUE_BODY_FALLBACK
                if dependencies_remote
                else DataSource.LOCAL_SQLITE if flow_state else None
            ),
            # Execution: local-only
            worktree_path=(flow_state.get("worktree_path") if flow_state else None),
            actor=(flow_state.get("latest_actor") if flow_state else None),
        )

        # Exit degraded mode if remote read succeeded
        if issue_number and blocked_reason_remote is not None:
            degraded = get_degraded_manager()
            degraded.exit_degraded_mode()

        return truth

    def _read_remote_collaboration(
        self,
        branch: str,
        issue_number: int,
    ) -> dict | None:
        """Read collaboration fields from issue body projection.

        Args:
            branch: Branch name
            issue_number: Issue number (required)

        Returns:
            Dict with blocked_reason/blocked_by_issue/dependencies from body,
            or None if read failed
        """
        from vibe3.clients.github_client import GitHubClient
        from vibe3.services.issue_body_service import parse_projection_with_fallback

        client = GitHubClient()

        try:
            body = client.get_issue_body(issue_number)
            if not body:
                return None

            projection = parse_projection_with_fallback(body)

            return {
                "blocked_reason": projection.blocked_reason,
                "blocked_by_issue": (
                    projection.blocked_by[0] if projection.blocked_by else None
                ),
                "dependencies": projection.dependencies,
            }
        except Exception:
            return None
