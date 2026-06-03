"""Shared issue dispatch eligibility policy."""

from __future__ import annotations

from dataclasses import dataclass

from vibe3.models import IssueInfo, IssueState
from vibe3.services.label_utils import has_manager_assignee


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
        reasons: list[DispatchExclusion] = []

        if issue.state is None:
            reasons.append(
                DispatchExclusion("missing_state_label", "missing state/* label")
            )
        elif issue.state == IssueState.BLOCKED:
            reasons.append(
                DispatchExclusion("blocked_state", "blocked issues require resume")
            )

        if "roadmap/rfc" in issue.labels:
            reasons.append(DispatchExclusion("roadmap_rfc", "roadmap RFC"))
        if "roadmap/epic" in issue.labels:
            reasons.append(DispatchExclusion("roadmap_epic", "roadmap epic"))
        if self._supervisor_label in issue.labels:
            reasons.append(DispatchExclusion("supervisor_issue", "supervisor issue"))

        if not has_manager_assignee(issue.assignees, self._manager_usernames):
            if not issue.assignees:
                reasons.append(
                    DispatchExclusion(
                        "missing_manager_assignee", "missing manager assignee"
                    )
                )
            else:
                reasons.append(
                    DispatchExclusion("non_manager_assignee", "assignee is not manager")
                )

        return reasons

    def is_dispatchable(self, issue: IssueInfo) -> bool:
        return not self.exclusion_reasons(issue)
