"""Usecase helpers for PR ready command orchestration."""

from typing import TYPE_CHECKING, Callable

from vibe3.models.pr import PRResponse

if TYPE_CHECKING:
    from vibe3.services.pr_service import PRService


class PrReadyAbortedError(RuntimeError):
    """Raised when user cancels PR ready confirmation."""


class PrReadyUsecase:
    """Coordinate PR ready sequencing while keeping UI in command layer."""

    def __init__(
        self,
        pr_service: "PRService",
        confirmer: Callable[[int], bool] | None = None,
    ) -> None:
        self.pr_service = pr_service
        self.confirmer = confirmer

    def mark_ready(
        self,
        pr_number: int,
        yes: bool,
        requested_reviewers: list[str] | None = None,
    ) -> PRResponse:
        """Enforce confirmation, then mark PR ready with optional AI review request."""
        current_pr = self.pr_service.get_pr(pr_number)
        if current_pr is not None and not current_pr.draft:
            # Already ready, update briefing and request review
            return self.pr_service.mark_ready(
                pr_number, requested_reviewers=requested_reviewers
            )

        if not yes and self.confirmer is not None and not self.confirmer(pr_number):
            raise PrReadyAbortedError("aborted by user")
        return self.pr_service.mark_ready(
            pr_number, requested_reviewers=requested_reviewers
        )
