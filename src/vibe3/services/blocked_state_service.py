"""Unified blocked state management service.

This service provides a single entry point for managing blocked state across
three data sources: database, issue body, and issue labels.

Design Principles:
1. Issue body + labels = Authoritative truth (remote-first)
2. Database = Performance cache (local optimization)
3. Qualify gate = Cache synchronizer (ensures coherence)

Usage:
    service = BlockedStateService()

    # Block a flow
    service.block(
        branch="task/issue-123",
        reason="Worktree corrupted",
        blocked_by_issue=456,
        actor="executor/agent"
    )

    # Unblock a flow
    service.unblock(
        branch="task/issue-123",
        target_state=IssueState.READY,
        actor="human:resume"
    )

    # Sync cache before dispatch
    state = service.sync_cache_from_truth(branch, issue_number)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.issue_body import FlowStateProjection
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_timeline_service import FlowTimelineService
from vibe3.services.issue_body_service import merge_projection, parse_projection
from vibe3.services.label_service import LabelService

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient


@dataclass
class BlockedState:
    """Represents blocked state from a single source."""

    is_blocked: bool
    blocked_reason: str | None = None
    blocked_by: list[int] | None = None
    state: str | None = None  # "active", "blocked", "done", etc.

    @classmethod
    def not_blocked(cls) -> BlockedState:
        """Create a non-blocked state."""
        return cls(is_blocked=False)

    @classmethod
    def blocked(
        cls,
        reason: str,
        blocked_by: list[int] | None = None,
    ) -> BlockedState:
        """Create a blocked state."""
        return cls(
            is_blocked=True,
            blocked_reason=reason,
            blocked_by=blocked_by or [],
            state="blocked",
        )


@dataclass
class ConsistencyReport:
    """Report on three-source consistency."""

    database_state: BlockedState
    body_state: BlockedState
    label_state: BlockedState

    @property
    def is_consistent(self) -> bool:
        """True if all three sources agree on blocked status."""
        # All should agree on is_blocked
        return (
            self.database_state.is_blocked == self.body_state.is_blocked
            and self.body_state.is_blocked == self.label_state.is_blocked
        )

    @property
    def authoritative_state(self) -> BlockedState:
        """Returns the truth-source state (issue body)."""
        return self.body_state


class BlockedStateService:
    """Unified blocked state management service.

    Manages blocked state across three data sources with clear ownership:

    Truth Hierarchy:
        Issue body + labels = Authoritative (remote-first)
        Database = Cache (performance optimization)

    Write Order (for atomicity):
        1. Issue body (truth) - if this fails, abort
        2. Database (cache) - non-critical, can repair later
        3. Labels (signal) - non-critical, can repair later
    """

    def __init__(
        self,
        store: SQLiteClient | None = None,
        github_client: GitHubClient | None = None,
        label_service: LabelService | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            store: SQLite client for database operations
            github_client: GitHub client for issue body operations
            label_service: Label service for issue label operations
        """
        self.store = store
        self.github = github_client or GitHubClient()
        self.label_service = label_service or LabelService()

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
        """Atomically set blocked state in all three sources.

        Write order ensures truth-source is updated first:
        1. Issue body (truth) - critical
        2. Database (cache) - non-critical
        3. Labels (signal) - non-critical

        Args:
            branch: Branch name
            reason: Blocking reason
            blocked_by_issue: Optional blocking issue number
            actor: Actor performing the block
            issue_number: Optional issue number (for body projection)
        """
        logger.bind(
            domain="blocked_state",
            action="block",
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
        ).info("Blocking flow")

        # Step 1: Write to issue body (truth source)
        if issue_number:
            try:
                self._write_body_projection(
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
                # Critical failure - abort
                raise

        # Step 2: Write to database (cache)
        if self.store:
            try:
                self._write_database_cache(
                    branch=branch,
                    reason=reason,
                    blocked_by_issue=blocked_by_issue,
                    actor=actor,
                )
            except Exception as exc:
                # Non-critical - log and continue
                logger.bind(
                    domain="blocked_state",
                    action="block",
                    branch=branch,
                ).warning(f"Failed to write database cache: {exc}")

        # Step 3: Write to labels (signal)
        if issue_number:
            try:
                self._write_label_state(
                    issue_number=issue_number,
                    target_state=IssueState.BLOCKED,
                    actor=actor,
                )
            except Exception as exc:
                # Non-critical - log and continue
                logger.bind(
                    domain="blocked_state",
                    action="block",
                    branch=branch,
                ).warning(f"Failed to write label state: {exc}")

        # Step 4: Write timeline event
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
        """Atomically clear blocked state in all three sources.

        Write order ensures truth-source is cleared first:
        1. Issue body (truth) - critical
        2. Database (cache) - non-critical
        3. Labels (signal) - non-critical

        Args:
            branch: Branch name
            target_state: Target state after unblocking
            actor: Actor performing the unblock
            issue_number: Optional issue number (for body projection)
        """
        logger.bind(
            domain="blocked_state",
            action="unblock",
            branch=branch,
            target_state=target_state.value,
        ).info("Unblocking flow")

        # Step 1: Clear issue body (truth source)
        if issue_number:
            try:
                self._clear_body_projection(issue_number=issue_number)
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="unblock",
                    branch=branch,
                ).error(f"Failed to clear issue body projection: {exc}")
                # Critical failure - abort
                raise

        # Step 2: Clear database (cache)
        if self.store:
            try:
                self._clear_database_cache(branch=branch, actor=actor)
            except Exception as exc:
                # Non-critical - log and continue
                logger.bind(
                    domain="blocked_state",
                    action="unblock",
                    branch=branch,
                ).warning(f"Failed to clear database cache: {exc}")

        # Step 3: Clear labels (signal)
        if issue_number:
            try:
                self._write_label_state(
                    issue_number=issue_number,
                    target_state=target_state,
                    actor=actor,
                )
            except Exception as exc:
                # Non-critical - log and continue
                logger.bind(
                    domain="blocked_state",
                    action="unblock",
                    branch=branch,
                ).warning(f"Failed to write label state: {exc}")

        # Step 4: Write timeline event
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
        """Check if flow is blocked (reads from authoritative truth).

        Args:
            branch: Branch name
            issue_number: Issue number

        Returns:
            True if blocked, False otherwise
        """
        state = self.resolve_truth(branch, issue_number)
        return state.is_blocked

    def get_blocked_reason(
        self,
        branch: str,
        issue_number: int,
    ) -> str | None:
        """Get blocked reason from authoritative truth.

        Args:
            branch: Branch name
            issue_number: Issue number

        Returns:
            Blocked reason string or None
        """
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

        Args:
            branch: Branch name
            reason: Blocked reason (None to preserve existing)
            blocked_by_issue: Blocking issue number
            actor: Actor performing the write
        """
        self._write_database_cache(
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
        """Synchronize local cache (DB) from authoritative truth (body).

        This is called by qualify gate before dispatch to ensure cache
        is coherent with the truth source.

        Args:
            branch: Branch name
            issue_number: Issue number

        Returns:
            Current blocked state after sync
        """
        # Read authoritative truth
        truth_state = self._read_body_projection(issue_number)

        # Read current cache
        cache_state = self._read_database_cache(branch) if self.store else None

        # Check if sync needed - sync when blocked-ness OR reason/by_issue differ
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

            # Update cache to match truth
            if truth_state.is_blocked:
                self._write_database_cache(
                    branch=branch,
                    reason=truth_state.blocked_reason,
                    blocked_by_issue=(
                        truth_state.blocked_by[0] if truth_state.blocked_by else None
                    ),
                    actor="system:sync",
                )
            else:
                self._clear_database_cache(branch=branch, actor="system:sync")

        return truth_state

    def resolve_truth(
        self,
        branch: str,
        issue_number: int,
    ) -> BlockedState:
        """Read authoritative truth from issue body.

        Fallback to database cache if body read fails.

        Args:
            branch: Branch name
            issue_number: Issue number

        Returns:
            Blocked state from truth source (or cache fallback)
        """
        # Try to read from issue body (truth)
        try:
            return self._read_body_projection(issue_number)
        except Exception as exc:
            logger.bind(
                domain="blocked_state",
                action="resolve_truth",
                branch=branch,
                issue_number=issue_number,
            ).warning(f"Failed to read issue body, falling back to cache: {exc}")

            # Fallback to database cache
            if self.store:
                return self._read_database_cache(branch)

            # No fallback available
            return BlockedState.not_blocked()

    def validate_consistency(
        self,
        branch: str,
        issue_number: int,
    ) -> ConsistencyReport:
        """Validate consistency across all three sources.

        Args:
            branch: Branch name
            issue_number: Issue number

        Returns:
            ConsistencyReport with states from all sources
        """
        database_state = (
            self._read_database_cache(branch)
            if self.store
            else BlockedState.not_blocked()
        )
        body_state = self._read_body_projection(issue_number)
        label_state = self._read_label_state(issue_number)

        return ConsistencyReport(
            database_state=database_state,
            body_state=body_state,
            label_state=label_state,
        )

    # ========================================================================
    # Private: Write Operations
    # ========================================================================

    def _write_body_projection(
        self,
        issue_number: int,
        reason: str | None,
        blocked_by_issue: int | None,
    ) -> None:
        """Write blocked state to issue body projection.

        Raises:
            RuntimeError: If issue body cannot be read or updated
        """
        current_body = self.github.get_issue_body(issue_number)
        if current_body is None:
            raise RuntimeError(
                f"Failed to read issue body for projection: issue #{issue_number}"
            )

        # Parse existing projection
        projection = parse_projection(current_body)

        # Merge blocked_by (deduplicate)
        existing_blocked_by = set(projection.blocked_by)
        if blocked_by_issue is not None:
            new_blocked_by = sorted(existing_blocked_by | {blocked_by_issue})
        else:
            new_blocked_by = list(existing_blocked_by)

        # Build new projection
        new_projection = FlowStateProjection(
            state="blocked",
            blocked_by=new_blocked_by,
            blocked_reason=reason,
            dependencies=projection.dependencies,
        )

        # Merge and update
        merged = merge_projection(current_body, new_projection)
        if not self.github.update_issue_body(issue_number, merged):
            raise RuntimeError(
                f"Failed to update issue body projection: issue #{issue_number}"
            )

    def _clear_body_projection(self, issue_number: int) -> None:
        """Clear blocked state from issue body projection.

        Raises:
            RuntimeError: If issue body cannot be read or updated
        """
        current_body = self.github.get_issue_body(issue_number)
        if current_body is None:
            raise RuntimeError(
                f"Failed to read issue body for clearing: issue #{issue_number}"
            )

        # Parse existing projection
        projection = parse_projection(current_body)

        # Clear blocked fields, preserve dependencies
        cleared = FlowStateProjection(
            state="active",
            blocked_by=[],
            blocked_reason=None,
            dependencies=projection.dependencies,
        )

        # Merge and update
        merged = merge_projection(current_body, cleared)
        if not self.github.update_issue_body(issue_number, merged):
            raise RuntimeError(
                f"Failed to clear issue body projection: issue #{issue_number}"
            )

    def _write_database_cache(
        self,
        branch: str,
        reason: str | None,
        blocked_by_issue: int | None,
        actor: str,
    ) -> None:
        """Write blocked state to database cache."""
        if not self.store:
            return
        self.store.update_flow_state(
            branch,
            flow_status="blocked",
            blocked_reason=reason,
            blocked_by_issue=blocked_by_issue,
            latest_actor=actor,
        )

    def _clear_database_cache(self, branch: str, actor: str) -> None:
        """Clear blocked state from database cache."""
        if not self.store:
            return
        self.store.update_flow_state(
            branch,
            flow_status="active",
            blocked_reason=None,
            blocked_by_issue=None,
            latest_actor=actor,
        )

    def _write_label_state(
        self,
        issue_number: int,
        target_state: IssueState,
        actor: str = "system",
    ) -> None:
        """Write state to issue labels."""
        self.label_service.confirm_issue_state(
            issue_number,
            target_state,
            actor=actor,
            force=True,
        )

    # ========================================================================
    # Private: Read Operations
    # ========================================================================

    def _read_body_projection(self, issue_number: int) -> BlockedState:
        """Read blocked state from issue body projection."""
        body = self.github.get_issue_body(issue_number)
        if not body:
            return BlockedState.not_blocked()

        projection = parse_projection(body)

        return BlockedState(
            is_blocked=(
                projection.state == "blocked"
                or projection.blocked_reason is not None
                or bool(projection.blocked_by)
            ),
            blocked_reason=projection.blocked_reason,
            blocked_by=projection.blocked_by,
            state=projection.state,
        )

    def _read_database_cache(self, branch: str) -> BlockedState:
        """Read blocked state from database cache."""
        if not self.store:
            return BlockedState.not_blocked()
        flow_state = self.store.get_flow_state(branch)
        if not flow_state:
            return BlockedState.not_blocked()

        blocked_reason = flow_state.get("blocked_reason")
        blocked_by_issue = flow_state.get("blocked_by_issue")
        flow_status = flow_state.get("flow_status")

        return BlockedState(
            is_blocked=(
                flow_status == "blocked"
                or blocked_reason is not None
                or blocked_by_issue is not None
            ),
            blocked_reason=blocked_reason,
            blocked_by=[blocked_by_issue] if blocked_by_issue else [],
            state=flow_status,
        )

    def _read_label_state(self, issue_number: int) -> BlockedState:
        """Read blocked state from issue labels."""
        try:
            issue = self.github.view_issue(issue_number)
            if not isinstance(issue, dict):
                return BlockedState.not_blocked()
            labels = issue.get("labels", [])
            label_names = [
                label.get("name") for label in labels if isinstance(label, dict)
            ]

            is_blocked = "state/blocked" in label_names

            return BlockedState(
                is_blocked=is_blocked,
                state="blocked" if is_blocked else None,
            )
        except Exception:
            return BlockedState.not_blocked()
