"""Protocol definitions for flow services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from vibe3.models import IssueInfo


class FlowBootstrapProtocol(Protocol):
    """Protocol for flow bootstrapping operations.

    This protocol defines the interface required by FlowRebuildUsecase
    to break the circular dependency with FlowOrchestratorService.
    """

    def bootstrap_issue_flow(
        self,
        issue: IssueInfo,
        *,
        branch: str,
        slug: str | None = ...,
        source: str = ...,
        actor: str | None = ...,
        initiated_by: str | None = ...,
        ensure_worktree: bool = ...,
        reactivate_existing: bool = ...,
        related_issue_numbers: tuple[int, ...] = ...,
        dependency_issue_numbers: tuple[int, ...] = ...,
        blocked_reason: str | None = ...,
        skip_git: bool = ...,
    ) -> dict[str, Any]:
        """Bootstrap a flow for an issue.

        Default values (matched by concrete implementation):
            slug: None (resolved to issue-{number})
            source: "dispatch"
            actor: None
            initiated_by: None
            ensure_worktree: False
            reactivate_existing: False
            related_issue_numbers: ()
            dependency_issue_numbers: ()
            blocked_reason: None
            skip_git: False

        Args:
            issue: The issue to create a flow for
            branch: Target branch name
            slug: Flow slug (defaults to issue-{number})
            source: Source identifier
            actor: Actor identifier
            initiated_by: Initiation source
            ensure_worktree: Whether to create a worktree
            reactivate_existing: Whether to reactivate existing flow
            related_issue_numbers: Related issue numbers
            dependency_issue_numbers: Dependency issue numbers
            blocked_reason: Reason for blocked state (if applicable)
            skip_git: Skip Git operations (for placeholder flows)

        Returns:
            Flow creation result dictionary
        """
        ...
