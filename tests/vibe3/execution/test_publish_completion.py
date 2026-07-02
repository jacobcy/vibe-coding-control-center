"""Tests for the sole code-owned normal state transition."""

from unittest.mock import MagicMock

import pytest

from vibe3.execution.publish_completion import PublishPRRefCompensationService
from vibe3.models import IssueState, PRResponse, PRState


def _open_pr(number: int, head_branch: str = "task/issue-42") -> PRResponse:
    return PRResponse(
        number=number,
        title=f"PR {number}",
        state=PRState.OPEN,
        head_branch=head_branch,
        base_branch="main",
        url=f"https://example.test/pull/{number}",
    )


@pytest.fixture
def dependencies():
    github = MagicMock()
    labels = MagicMock()
    recorder = MagicMock()
    recorder.would_exceed.return_value = False
    return github, labels, recorder


def test_new_pr_advances_merge_ready_to_handoff(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = [_open_pr(91)]
    labels.confirm_issue_state.return_value = "advanced"
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        before_pr_ref=None,
        actor="agent:executor",
    )

    assert result.completed is True
    assert result.pr_number == 91
    labels.confirm_issue_state.assert_called_once_with(
        42, IssueState.HANDOFF, actor="agent:executor", force=False
    )
    recorder.record_confirmed.assert_called_once_with(
        branch="task/issue-42",
        from_state="state/merge-ready",
        to_state="state/handoff",
        actor="agent:executor",
        issue_number=42,
    )


def test_existing_open_pr_never_qualifies(dependencies) -> None:
    github, labels, recorder = dependencies
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset({90}),
        before_pr_ref=None,
        actor="agent:executor",
    )

    assert result.completed is False
    assert "existed before" in result.reason
    github.list_prs_for_branch.assert_not_called()
    labels.confirm_issue_state.assert_not_called()


def test_existing_pr_ref_never_qualifies(dependencies) -> None:
    """Compensation is rejected when before_pr_ref already exists."""
    github, labels, recorder = dependencies
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        before_pr_ref="PR-123",
        actor="agent:executor",
    )

    assert result.completed is False
    assert "pr_ref already exists" in result.reason
    github.list_prs_for_branch.assert_not_called()
    labels.confirm_issue_state.assert_not_called()


def test_wrong_branch_rejects(dependencies) -> None:
    """Compensation is rejected when new PR head_branch doesn't match current branch."""
    github, labels, recorder = dependencies
    # PR belongs to a different branch
    github.list_prs_for_branch.return_value = [
        _open_pr(91, head_branch="task/issue-99")
    ]
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        before_pr_ref=None,
        actor="agent:executor",
    )

    assert result.completed is False
    assert "does not match current branch" in result.reason
    labels.confirm_issue_state.assert_not_called()


def test_no_new_pr_never_qualifies_even_with_cached_ref(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = []
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        before_pr_ref=None,
        actor="agent:executor",
    )

    assert result.completed is False
    labels.confirm_issue_state.assert_not_called()


def test_ambiguous_multiple_new_prs_never_qualify(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = [_open_pr(91), _open_pr(92)]
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        before_pr_ref=None,
        actor="agent:executor",
    )

    assert result.completed is False
    assert "exactly one" in result.reason
    labels.confirm_issue_state.assert_not_called()


def test_failed_label_write_never_records_success(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = [_open_pr(91)]
    labels.confirm_issue_state.return_value = "blocked"
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        before_pr_ref=None,
        actor="agent:executor",
    )

    assert result.completed is False
    assert "not applied" in result.reason
    recorder.record_confirmed.assert_not_called()


def test_exhausted_transition_budget_never_writes_label(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = [_open_pr(91)]
    recorder.would_exceed.return_value = True
    service = PublishPRRefCompensationService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        before_pr_ref=None,
        actor="agent:executor",
    )

    assert result.completed is False
    assert "limit" in result.reason
    labels.confirm_issue_state.assert_not_called()
