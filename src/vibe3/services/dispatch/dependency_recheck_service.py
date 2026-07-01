"""Dependency recheck service.

Handles IssueResolvedDependency events by triggering
BlockedStateService.reconcile_blocked for each dependent flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models import IssueState

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.models.domain_events import IssueResolvedDependency
    from vibe3.services.flow.blocked_state_service import BlockedStateService


@dataclass(frozen=True)
class RecheckResult:
    """Result of dependency recheck operation."""

    issue_number: int
    dependents_checked: int
    unblocked: int
    still_blocked: int
    errors: int


class DependencyRecheckService:
    """Service that re-evaluates blocked flows when a dependency issue closes."""

    MAX_DEPENDENTS_PER_EVENT = 25  # Bound cascading re-evaluations

    def __init__(
        self,
        store: SQLiteClient,
        github_client: GitHubClient,
        blocked_state_service_cls: type[BlockedStateService] | None = None,
    ) -> None:
        """Initialize dependency recheck service."""
        self.store = store
        self.github_client = github_client
        # Import here to avoid circular dependency
        if blocked_state_service_cls is None:
            from vibe3.services.flow.blocked_state_service import BlockedStateService

            blocked_state_service_cls = BlockedStateService
        self.blocked_state_service_cls = blocked_state_service_cls

    def handle_issue_resolved(self, event: IssueResolvedDependency) -> RecheckResult:
        """Handle IssueResolvedDependency event by re-evaluating dependent flows.

        Args:
            event: IssueResolvedDependency event with closed issue number.

        Returns:
            RecheckResult with counts of dependents checked and outcomes.
        """
        branches = self.store.get_issue_dependents(event.issue_number)

        if not branches:
            logger.bind(
                domain="dispatch",
                action="dependency_recheck",
                issue_number=event.issue_number,
            ).debug("No dependents found for closed issue")
            return RecheckResult(
                issue_number=event.issue_number,
                dependents_checked=0,
                unblocked=0,
                still_blocked=0,
                errors=0,
            )

        # Bound cascading re-evaluations
        if len(branches) > self.MAX_DEPENDENTS_PER_EVENT:
            logger.bind(
                domain="dispatch",
                action="dependency_recheck",
                issue_number=event.issue_number,
                dependents_count=len(branches),
                max_dependents=self.MAX_DEPENDENTS_PER_EVENT,
            ).warning(
                f"Too many dependents ({len(branches)}); "
                f"slicing to first {self.MAX_DEPENDENTS_PER_EVENT}"
            )
            branches = branches[: self.MAX_DEPENDENTS_PER_EVENT]

        # Track outcomes
        unblocked = 0
        still_blocked = 0
        errors = 0

        service = self.blocked_state_service_cls(
            store=self.store,
            github_client=self.github_client,
        )

        for branch in branches:
            # Resolve task issue number for this branch
            issue_number = self.store.get_task_issue_number(branch)
            if issue_number is None:
                logger.bind(
                    domain="dispatch",
                    action="dependency_recheck",
                    branch=branch,
                    upstream_issue=event.issue_number,
                ).debug("Branch has no task issue; skipping")
                still_blocked += 1
                continue

            try:
                result = service.reconcile_blocked(
                    issue_number,
                    branch,
                    clear_reason=False,
                    actor="system:dispatch:dep-recheck",
                )

                if result == IssueState.READY:
                    unblocked += 1
                    logger.bind(
                        domain="dispatch",
                        action="dependency_recheck",
                        branch=branch,
                        issue_number=issue_number,
                        upstream_issue=event.issue_number,
                        outcome="unblocked",
                    ).info("Dependent flow unblocked after upstream closure")
                elif result is None:
                    # None means stay blocked (degraded mode or still has deps)
                    still_blocked += 1
                    logger.bind(
                        domain="dispatch",
                        action="dependency_recheck",
                        branch=branch,
                        issue_number=issue_number,
                        upstream_issue=event.issue_number,
                        outcome="still_blocked",
                    ).debug("Dependent flow remains blocked")
                else:
                    # Other state (e.g., still blocked with open deps)
                    still_blocked += 1
            except Exception as exc:
                errors += 1
                logger.bind(
                    domain="dispatch",
                    action="dependency_recheck",
                    branch=branch,
                    issue_number=issue_number,
                    upstream_issue=event.issue_number,
                    error=str(exc),
                ).error(f"Failed to reconcile dependent flow: {exc}")

        logger.bind(
            domain="dispatch",
            action="dependency_recheck",
            issue_number=event.issue_number,
            dependents_checked=len(branches),
            unblocked=unblocked,
            still_blocked=still_blocked,
            errors=errors,
            merged=event.merged,
        ).info("Dependency recheck complete")

        return RecheckResult(
            issue_number=event.issue_number,
            dependents_checked=len(branches),
            unblocked=unblocked,
            still_blocked=still_blocked,
            errors=errors,
        )
