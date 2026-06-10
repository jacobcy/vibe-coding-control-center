"""Shared issue dispatch eligibility policy."""

from __future__ import annotations

from dataclasses import dataclass

from vibe3.models import IssueInfo
from vibe3.services.shared.labels import classify_dispatch_eligibility


@dataclass(frozen=True)
class DispatchExclusion:
    """Structured reason why an issue should not be auto-dispatched."""

    code: str
    message: str


class IssueDispatchPolicy:
    """Evaluate whether an issue may enter automatic dispatch."""

    def __init__(
        self,
        *,
        supervisor_label: str,
        manager_usernames: tuple[str, ...],
    ) -> None:
        self._supervisor_label = supervisor_label
        self._manager_usernames = manager_usernames

    def exclusion_reasons(self, issue: IssueInfo) -> list[DispatchExclusion]:
        return classify_dispatch_eligibility(
            labels=issue.labels,
            assignees=issue.assignees,
            supervisor_label=self._supervisor_label,
            manager_usernames=self._manager_usernames,
        )

    def is_dispatchable(self, issue: IssueInfo) -> bool:
        return not self.exclusion_reasons(issue)
