"""Tests for the sole code-owned normal state transition."""

from unittest.mock import MagicMock

import pytest

from vibe3.execution.publish_completion import PublishCompletionService
from vibe3.models import IssueState, PRResponse, PRState


def _open_pr(number: int) -> PRResponse:
    return PRResponse(
        number=number,
        title=f"PR {number}",
        state=PRState.OPEN,
        head_branch="task/issue-42",
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
    service = PublishCompletionService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
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
    service = PublishCompletionService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset({90}),
        actor="agent:executor",
    )

    assert result.completed is False
    assert "existed before" in result.reason
    github.list_prs_for_branch.assert_not_called()
    labels.confirm_issue_state.assert_not_called()


def test_no_new_pr_never_qualifies_even_with_cached_ref(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = []
    service = PublishCompletionService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        actor="agent:executor",
    )

    assert result.completed is False
    labels.confirm_issue_state.assert_not_called()


def test_ambiguous_multiple_new_prs_never_qualify(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = [_open_pr(91), _open_pr(92)]
    service = PublishCompletionService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        actor="agent:executor",
    )

    assert result.completed is False
    assert "exactly one" in result.reason
    labels.confirm_issue_state.assert_not_called()


def test_failed_label_write_never_records_success(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = [_open_pr(91)]
    labels.confirm_issue_state.return_value = "blocked"
    service = PublishCompletionService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        actor="agent:executor",
    )

    assert result.completed is False
    assert "not applied" in result.reason
    recorder.record_confirmed.assert_not_called()


def test_exhausted_transition_budget_never_writes_label(dependencies) -> None:
    github, labels, recorder = dependencies
    github.list_prs_for_branch.return_value = [_open_pr(91)]
    recorder.would_exceed.return_value = True
    service = PublishCompletionService(github, labels, recorder)

    result = service.try_complete(
        issue_number=42,
        branch="task/issue-42",
        before_state_labels=frozenset({"state/merge-ready"}),
        before_open_pr_numbers=frozenset(),
        actor="agent:executor",
    )

    assert result.completed is False
    assert "limit" in result.reason
    labels.confirm_issue_state.assert_not_called()
