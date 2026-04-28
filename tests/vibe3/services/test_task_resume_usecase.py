"""Tests for task resume usecase error reporting."""

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.task_resume_usecase import TaskResumeUsecase


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
    usecase.candidates.verify_issue_state_for_resume = MagicMock(return_value=True)
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
    usecase.candidates.verify_issue_state_for_resume = MagicMock(return_value=True)
    usecase.operations.reset_issue_to_ready = MagicMock(side_effect=RuntimeError())

    result = usecase.resume_issues(dry_run=False)

    assert result["resumed"] == []
    assert result["skipped"] == [
        {"number": 432, "reason": "恢复操作失败: RuntimeError"}
    ]
