"""Tests for shared issue dispatch policy."""

from __future__ import annotations

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.issue.dispatch_policy import IssueDispatchPolicy


def _issue(
    *,
    state: IssueState | None = IssueState.READY,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
) -> IssueInfo:
    return IssueInfo(
        number=1,
        title="task",
        state=state,
        labels=labels if labels is not None else ["state/ready"],
        assignees=assignees if assignees is not None else ["vibe-manager-agent"],
    )


def test_ready_manager_issue_is_dispatchable() -> None:
    policy = IssueDispatchPolicy(
        supervisor_label="supervisor",
        manager_usernames=("vibe-manager-agent",),
    )

    assert policy.exclusion_reasons(_issue()) == []
    assert policy.is_dispatchable(_issue()) is True


def test_policy_reports_all_relevant_exclusion_reasons() -> None:
    policy = IssueDispatchPolicy(
        supervisor_label="supervisor",
        manager_usernames=("vibe-manager-agent",),
    )
    issue = _issue(
        state=None,
        labels=["roadmap/epic", "supervisor"],
        assignees=["jacobcy"],
    )

    reasons = policy.exclusion_reasons(issue)

    assert [reason.code for reason in reasons] == [
        "missing_state_label",
        "roadmap_epic",
        "supervisor_issue",
        "non_manager_assignee",
    ]
    assert policy.is_dispatchable(issue) is False


def test_blocked_and_rfc_are_not_dispatchable() -> None:
    policy = IssueDispatchPolicy(
        supervisor_label="supervisor",
        manager_usernames=("vibe-manager-agent",),
    )
    issue = _issue(
        state=IssueState.BLOCKED,
        labels=["state/blocked", "roadmap/rfc"],
    )

    assert [reason.code for reason in policy.exclusion_reasons(issue)] == [
        "blocked_state",
        "roadmap_rfc",
    ]
