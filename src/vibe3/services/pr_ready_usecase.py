"""Usecase helpers for PR ready command orchestration."""

from typing import Callable

from vibe3.models.orchestration import IssueState
from vibe3.models.pr import PRResponse
from vibe3.services.label_service import LabelService
from vibe3.services.pr_service import PRService


class PrReadyAbortedError(RuntimeError):
    """Raised when user cancels PR ready confirmation."""


class PrReadyUsecase:
    """Coordinate PR ready sequencing while keeping UI in command layer."""

    def __init__(
        self,
        pr_service: PRService,
        gate_runner: Callable[[int, bool], None],
        confirmer: Callable[[int], bool] | None = None,
        label_service: LabelService | None = None,
    ) -> None:
        self.pr_service = pr_service
        self.gate_runner = gate_runner
        self.confirmer = confirmer
        self.label_service = label_service or LabelService()

    def mark_ready(
        self,
        pr_number: int,
        yes: bool,
    ) -> PRResponse:
        """Run gates, enforce confirmation, then mark PR ready."""
        current_pr = self.pr_service.get_pr(pr_number)
        if current_pr is not None and not current_pr.draft:
            pr = self.pr_service.mark_ready(pr_number)
            self._sync_merge_ready_label(pr)
            return pr

        self.gate_runner(pr_number, yes)
        if not yes and self.confirmer is not None and not self.confirmer(pr_number):
            raise PrReadyAbortedError("aborted by user")
        pr = self.pr_service.mark_ready(pr_number)
        self._sync_merge_ready_label(pr)
        return pr

    def _sync_merge_ready_label(self, pr: PRResponse) -> None:
        """Sync linked task issue to state/merge-ready after PR becomes ready."""
        task_issue: int | None = None
        try:
            links = self.pr_service.store.get_issue_links(pr.head_branch)
        except Exception:
            links = []
        for link in links:
            if link.get("issue_role") == "task":
                task_issue = link.get("issue_number")
                break

        if task_issue is None:
            flow = self.pr_service.store.get_flow_state(pr.head_branch)
            if flow:
                task_issue = flow.get("task_issue_number")
        if task_issue is None:
            return
        self.label_service.confirm_issue_state(
            int(task_issue),
            IssueState.MERGE_READY,
            actor="pr:ready",
            force=True,
        )
