"""Tests for task resume usecase error reporting."""

import inspect
from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.task import TaskResumeUsecase


def _make_usecase() -> TaskResumeUsecase:
    return TaskResumeUsecase(
        status_service=MagicMock(),
        label_service=MagicMock(),
        flow_service=MagicMock(),
        git_client=MagicMock(),
        github_client=MagicMock(),
        issue_flow_service=MagicMock(),
    )


def test_resume_issues_surfaces_operation_error_in_skipped_reason() -> None:
    usecase = _make_usecase()
    candidate = {
        "number": 431,
        "title": "resume me",
        "state": IssueState.BLOCKED,
        "resume_kind": "blocked",
        "flow": None,
    }
    usecase.status_service.fetch_resume_candidates.return_value = [candidate]
    usecase.candidates.verify_issue_state_for_resume = MagicMock(
        return_value=(True, None)
    )
    usecase.operations.reset_issue_to_ready = MagicMock(
        side_effect=RuntimeError("scene cleanup failed")
    )

    result = usecase.resume_issues(dry_run=False)

    assert result["resumed"] == []
    assert result["skipped"] == [
        {"number": 431, "reason": "恢复操作失败: scene cleanup failed"}
    ]


def test_resume_issues_uses_exception_class_when_message_missing() -> None:
    usecase = _make_usecase()
    candidate = {
        "number": 432,
        "title": "resume me too",
        "state": IssueState.BLOCKED,
        "resume_kind": "blocked",
        "flow": None,
    }
    usecase.status_service.fetch_resume_candidates.return_value = [candidate]
    usecase.candidates.verify_issue_state_for_resume = MagicMock(
        return_value=(True, None)
    )
    usecase.operations.reset_issue_to_ready = MagicMock(side_effect=RuntimeError())

    result = usecase.resume_issues(dry_run=False)

    assert result["resumed"] == []
    assert result["skipped"] == [
        {"number": 432, "reason": "恢复操作失败: RuntimeError"}
    ]


def test_resume_issues_defaults_to_label_auto_and_skips_reset_comment() -> None:
    """Direct usecase callers must also get label-auto, not destructive rebuild."""
    usecase = _make_usecase()
    candidate = {
        "number": 303,
        "title": "resume me",
        "resume_kind": "blocked",
        "flow": MagicMock(branch="task/issue-303"),
    }
    usecase.status_service.fetch_resume_candidates.return_value = [candidate]
    usecase.candidates.verify_issue_state_for_resume = MagicMock(
        return_value=(True, None)
    )
    usecase.operations.reset_issue_to_ready = MagicMock()
    result = usecase.resume_issues(dry_run=False)

    assert result["resumed"] == [{"number": 303, "resume_kind": "blocked"}]
    call = usecase.operations.reset_issue_to_ready.call_args.kwargs
    assert call["label_state"] == ""


def test_resume_issues_has_no_all_task_candidate_mode() -> None:
    """Task resume usecase should not keep the old all-task reset selector."""
    params = inspect.signature(TaskResumeUsecase.resume_issues).parameters

    assert "candidate_mode" not in params


def test_verify_rejects_when_blocked_by_dependency_still_open() -> None:
    """Test that resume is rejected when blocked_by_issue is still OPEN."""
    usecase = _make_usecase()
    usecase.label_service.get_state.return_value = MagicMock(value="blocked")
    usecase.candidates._flow_service.get_flow_for_issue.return_value = {
        "blocked_by_issue": 999
    }

    # Mock GitHub client to return OPEN state
    usecase.candidates._github_client.view_issue.return_value = {
        "state": "OPEN",
        "labels": [],
    }
    can_resume, reason = usecase.candidates.verify_issue_state_for_resume(
        123, "blocked", None
    )

    assert can_resume is False
    assert "task #999 尚未关闭" in reason
    assert "(state=OPEN)" in reason


def test_verify_allows_when_blocked_by_dependency_closed() -> None:
    """Test that resume is allowed when blocked_by_issue is CLOSED."""
    usecase = _make_usecase()
    usecase.label_service.get_state.return_value = MagicMock(value="blocked")
    usecase.candidates._flow_service.get_flow_for_issue.return_value = {
        "blocked_by_issue": 999
    }

    # Mock GitHub client to return CLOSED state
    usecase.candidates._github_client.view_issue.return_value = {
        "state": "CLOSED",
        "labels": [],
    }
    can_resume, reason = usecase.candidates.verify_issue_state_for_resume(
        123, "blocked", None
    )

    assert can_resume is True
    assert reason is None


def test_verify_skips_check_when_blocked_by_issue_empty() -> None:
    """Test that dependency check is skipped when blocked_by_issue is None or 0."""
    usecase = _make_usecase()
    usecase.label_service.get_state.return_value = MagicMock(value="blocked")

    # Test with None
    usecase.candidates._flow_service.get_flow_for_issue.return_value = {
        "blocked_by_issue": None
    }
    can_resume, reason = usecase.candidates.verify_issue_state_for_resume(
        123, "blocked", None
    )
    assert can_resume is True
    assert reason is None

    # Test with 0
    usecase.candidates._flow_service.get_flow_for_issue.return_value = {
        "blocked_by_issue": 0
    }
    can_resume, reason = usecase.candidates.verify_issue_state_for_resume(
        123, "blocked", None
    )
    assert can_resume is True
    assert reason is None


def test_verify_refuses_when_gh_command_fails() -> None:
    """Test that resume is refused (fail-safe) when GitHub API fails."""
    usecase = _make_usecase()
    usecase.label_service.get_state.return_value = MagicMock(value="blocked")
    usecase.candidates._flow_service.get_flow_for_issue.return_value = {
        "blocked_by_issue": 999
    }

    # Mock GitHub client to fail (return None for not found)
    usecase.candidates._github_client.view_issue.return_value = None
    can_resume, reason = usecase.candidates.verify_issue_state_for_resume(
        123, "blocked", None
    )

    # Should fail-safe: refuse resume when cannot verify dependency
    assert can_resume is False
    assert "task #999" in reason
