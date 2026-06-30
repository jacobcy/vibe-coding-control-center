"""Low-level I/O operations for blocked state management.

This module handles reading/writing blocked state to individual sources:
- Issue body projection (truth source)
- Database cache
- Issue labels (signal)
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.models import FlowStateProjection, IssueState
from vibe3.services.flow.blocked_state_types import BlockedState
from vibe3.services.issue.body import merge_projection, parse_projection
from vibe3.services.shared.label_service import LabelService

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class BlockedStateIO:
    """Handles low-level read/write operations for blocked state."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        label_service: LabelService | None = None,
        store: SQLiteClient | None = None,
    ) -> None:
        self.github = github_client or GitHubClient()
        self.label_service = label_service or LabelService()
        self.store = store

    # ========================================================================
    # Write Operations
    # ========================================================================

    def write_projection(
        self,
        issue_number: int,
        projection: FlowStateProjection,
    ) -> None:
        """Write complete flow-state projection to issue body."""
        current_body = self.github.get_issue_body(issue_number)
        if current_body is None:
            raise RuntimeError(f"Failed to read issue body: issue #{issue_number}")
        merged = merge_projection(current_body, projection)
        if merged == current_body:
            return
        if not self.github.update_issue_body(issue_number, merged):
            raise RuntimeError(
                f"Failed to update issue body projection: issue #{issue_number}"
            )

    def write_body_projection(
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

        projection = parse_projection(current_body)

        existing_blocked_by = set(projection.blocked_by)
        if blocked_by_issue is not None:
            new_blocked_by = sorted(existing_blocked_by | {blocked_by_issue})
        else:
            new_blocked_by = list(existing_blocked_by)

        new_projection = FlowStateProjection(
            state="blocked",
            blocked_by=new_blocked_by,
            blocked_reason=reason,
        )

        merged = merge_projection(current_body, new_projection)
        if merged == current_body:
            return

        if not self.github.update_issue_body(issue_number, merged):
            raise RuntimeError(
                f"Failed to update issue body projection: issue #{issue_number}"
            )

    def clear_body_projection(self, issue_number: int) -> None:
        """Clear blocked state from issue body projection.

        Raises:
            RuntimeError: If issue body cannot be read or updated
        """
        current_body = self.github.get_issue_body(issue_number)
        if current_body is None:
            raise RuntimeError(
                f"Failed to read issue body for projection: issue #{issue_number}"
            )

        new_projection = FlowStateProjection(
            state="active",
            blocked_by=[],
            blocked_reason=None,
        )

        merged = merge_projection(current_body, new_projection)
        if merged == current_body:
            return

        if not self.github.update_issue_body(issue_number, merged):
            raise RuntimeError(
                f"Failed to clear issue body projection: issue #{issue_number}"
            )

    def write_database_cache(
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

    def clear_database_cache(self, branch: str, actor: str) -> None:
        """Clear blocked state from database cache.

        Also resets transition counters to allow flow to continue after
        being blocked by loop protection or AUP rejection threshold.
        """
        if not self.store:
            return

        # Reset transition_count and aup_rejection_count to allow flow
        # to continue after unblock. Without resetting aup_rejection_count,
        # the next AUP rejection would immediately re-block the flow since
        # the counter is already at or above the threshold.
        self.store.update_flow_state(
            branch,
            flow_status="active",
            blocked_reason=None,
            blocked_by_issue=None,
            transition_count=0,  # Reset loop protection counter
            aup_rejection_count=0,  # Reset AUP rejection counter
            last_aup_rejection_at=None,  # Clear AUP rejection timestamp
            latest_actor=actor,
        )

        # Clear transition history to reset per-pair loop detection
        try:
            with sqlite3.connect(self.store.db_path) as conn:
                self.store.clear_transition_history(conn, branch)
        except Exception as exc:
            # Non-critical: log and continue
            logger.bind(
                domain="blocked_state",
                action="clear_database_cache",
                branch=branch,
            ).warning(f"Failed to clear transition history: {exc}")

    def write_label_state(
        self,
        issue_number: int,
        target_state: IssueState,
        actor: str = "system",
        force: bool = False,
        normalize: bool = False,
    ) -> Literal["confirmed", "advanced", "blocked", "normalized"]:
        """Write state to issue labels.

        Args:
            issue_number: Issue number
            target_state: Target state to set
            actor: Actor performing the transition
            force: If True, bypass transition validation (for unblock/resume)
            normalize: If True, replace every remote state label with the target

        Returns:
            "confirmed": Already in target state
            "advanced": Transition succeeded
            "blocked": Transition rejected by state machine
            "normalized": Duplicate or stale state labels were replaced
        """
        if normalize:
            return self.label_service.replace_issue_state(
                issue_number,
                target_state,
                actor=actor,
            )
        return self.label_service.confirm_issue_state(
            issue_number,
            target_state,
            actor=actor,
            force=force,
        )

    # ========================================================================
    # Read Operations
    # ========================================================================

    def read_body_projection(self, issue_number: int) -> BlockedState:
        """Read blocked state from issue body projection."""
        try:
            body = self.github.get_issue_body(issue_number)
            if body is None:
                return BlockedState.not_blocked()

            projection = parse_projection(body)
            return BlockedState(
                is_blocked=projection.state == "blocked",
                blocked_reason=projection.blocked_reason,
                blocked_by=projection.blocked_by,
                state=projection.state,
            )
        except Exception as exc:
            logger.bind(
                domain="blocked_state",
                action="read_body",
                issue_number=issue_number,
            ).warning(f"Failed to read body projection: {exc}")
            return BlockedState.not_blocked()

    def read_database_cache(self, branch: str) -> BlockedState:
        """Read blocked state from database cache."""
        if not self.store:
            return BlockedState.not_blocked()

        try:
            flow_state = self.store.get_flow_state(branch)
            if not flow_state:
                return BlockedState.not_blocked()

            return BlockedState(
                is_blocked=flow_state.get("flow_status") == "blocked",
                blocked_reason=flow_state.get("blocked_reason"),
                blocked_by=(
                    [flow_state["blocked_by_issue"]]
                    if flow_state.get("blocked_by_issue")
                    else []
                ),
                state=flow_state.get("flow_status"),
            )
        except Exception as exc:
            logger.bind(
                domain="blocked_state",
                action="read_database",
                branch=branch,
            ).warning(f"Failed to read database cache: {exc}")
            return BlockedState.not_blocked()

    def read_label_state(self, issue_number: int) -> BlockedState:
        """Read blocked state from issue labels."""
        try:
            current_state = self.label_service.get_state(issue_number)
            return BlockedState(
                is_blocked=current_state == IssueState.BLOCKED,
                state=current_state.value if current_state else None,
            )
        except Exception as exc:
            logger.bind(
                domain="blocked_state",
                action="read_label",
                issue_number=issue_number,
            ).warning(f"Failed to read label state: {exc}")
            return BlockedState.not_blocked()
