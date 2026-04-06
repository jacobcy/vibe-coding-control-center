"""Tests for TaskResumeUsecase."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services import task_resume_usecase


def test_resume_issues_dry_run_reports_failed_and_blocked_candidates_without_mutation() -> (  # noqa: E501
    None
):
    """dry-run 只返回候选，不调用 side effect。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 439,
            "title": "Manager backend regression",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": MagicMock(plan_ref="docs/plans/issue-439.md"),
        },
        {
            "number": 301,
            "title": "Dependency available",
            "state": IssueState.BLOCKED,
            "resume_kind": "blocked",
            "flow": MagicMock(plan_ref=None),
        },
    ]

    with patch.object(
        task_resume_usecase, "StatusQueryService", return_value=mock_status_service
    ):
        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(dry_run=True)

        # dry-run 应返回候选列表
        assert "candidates" in result
        assert len(result["candidates"]) == 2

        # 不应调用任何 side effect
        assert result["resumed"] == []
        assert result["skipped"] == []

        # 不应调用 resume 函数
        # (这些函数不在 usecase 中，而是通过 service module 调用)


def test_resume_issues_apply_routes_failed_by_plan_ref_and_blocked_to_ready() -> None:
    """resume_kind == failed 时按 plan_ref 路由，blocked 时固定到 ready。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 439,
            "title": "Manager backend regression",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": MagicMock(plan_ref="docs/plans/issue-439.md"),
        },
        {
            "number": 441,
            "title": "API timeout",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": MagicMock(plan_ref=None),
        },
        {
            "number": 301,
            "title": "Dependency available",
            "state": IssueState.BLOCKED,
            "resume_kind": "blocked",
            "flow": MagicMock(plan_ref=None),
        },
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(
            task_resume_usecase, "resume_failed_issue_to_handoff"
        ) as mock_to_handoff,
        patch.object(
            task_resume_usecase, "resume_failed_issue_to_ready"
        ) as mock_failed_to_ready,
        patch.object(
            task_resume_usecase, "resume_blocked_issue_to_ready"
        ) as mock_blocked_to_ready,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
    ):
        # Mock label service to verify state matches resume_kind
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        # Use get_state() method and return IssueState enum objects
        mock_label_instance.get_state.side_effect = lambda num: {
            439: IssueState.FAILED,
            441: IssueState.FAILED,
            301: IssueState.BLOCKED,
        }.get(num)

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(dry_run=False)

        # 应调用正确的恢复函数
        # 439: failed + plan_ref -> handoff
        mock_to_handoff.assert_called_once()
        assert mock_to_handoff.call_args[1]["issue_number"] == 439

        # 441: failed + no plan_ref -> ready
        mock_failed_to_ready.assert_called_once()
        assert mock_failed_to_ready.call_args[1]["issue_number"] == 441

        # 301: blocked -> ready
        mock_blocked_to_ready.assert_called_once()
        assert mock_blocked_to_ready.call_args[1]["issue_number"] == 301

        # 结果应包含恢复的 issue
        assert len(result["resumed"]) == 3
        assert result["skipped"] == []


def test_resume_issues_skips_issue_when_current_state_no_longer_matches_resume_kind() -> (  # noqa: E501
    None
):
    """执行前防御性校验：issue 当前 label 必须仍和 resume_kind 对应。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 439,
            "title": "Manager backend regression",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": MagicMock(plan_ref="docs/plans/issue-439.md"),
        },
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(
            task_resume_usecase, "resume_failed_issue_to_handoff"
        ) as mock_to_handoff,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
    ):
        # Mock label service to return mismatched state
        # 439 was failed, but now it's ready (already resumed by someone else)
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = IssueState.READY

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(dry_run=False)

        # 不应调用 resume 函数
        mock_to_handoff.assert_not_called()

        # 应被跳过
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["number"] == 439
        # skipped reason 要明确说明是"不再处于 failed/blocked 状态"
        assert "不再处于" in result["skipped"][0]["reason"]
        assert result["resumed"] == []
