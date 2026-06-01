"""Low-level I/O operations for blocked state management.

This module handles reading/writing blocked state to individual sources:
- Issue body projection (truth source)
- Database cache
- Issue labels (signal)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.issue_body import FlowStateProjection
from vibe3.models.orchestration import IssueState
from vibe3.services.blocked_state_types import BlockedState
from vibe3.services.issue_body_service import merge_projection, parse_projection
from vibe3.services.label_service import LabelService

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
            dependencies=projection.dependencies,
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

        projection = parse_projection(current_body)

        new_projection = FlowStateProjection(
            state="active",
            blocked_by=[],
            blocked_reason=None,
            dependencies=projection.dependencies,
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
        """Clear blocked state from database cache."""
        if not self.store:
            return
        self.store.update_flow_state(
            branch,
            flow_status="active",
            blocked_reason=None,
            failed_reason=None,  # Also clear failed_reason for consistency
            blocked_by_issue=None,
            latest_actor=actor,
        )

    def write_label_state(
        self,
        issue_number: int,
        target_state: IssueState,
        actor: str = "system",
        force: bool = False,
    ) -> Literal["confirmed", "advanced", "blocked"]:
        """Write state to issue labels.

        Args:
            issue_number: Issue number
            target_state: Target state to set
            actor: Actor performing the transition
            force: If True, bypass transition validation (for unblock/resume)

        Returns:
            "confirmed": Already in target state
            "advanced": Transition succeeded
            "blocked": Transition rejected by state machine
        """
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
