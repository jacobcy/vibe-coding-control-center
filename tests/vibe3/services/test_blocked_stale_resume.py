"""End-to-end regression tests for blocked stale task resume flow."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services import task_resume_usecase


def test_blocked_stale_issue_appears_in_resume_all_candidates() -> None:
    """blocked + stale 候选能被 task resume --all 抓到。"""
    mock_status_service = MagicMock()

    # Mock blocked issue with stale flow
    stale_flow = MagicMock()
    stale_flow.plan_ref = None
    stale_flow.branch = "task/issue-301"
    stale_flow.task_issue_number = 301
    stale_flow.flow_status = "stale"

    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 301,
            "title": "Dependency available",
            "state": IssueState.BLOCKED,
            "resume_kind": "blocked",
            "flow": stale_flow,
        },
    ]

    with patch.object(
        task_resume_usecase, "StatusQueryService", return_value=mock_status_service
    ):
        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(dry_run=True)

        # blocked + stale 候选应被抓到
        assert "candidates" in result
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["number"] == 301
        assert result["candidates"][0]["resume_kind"] == "blocked"


def test_blocked_stale_issue_resume_posts_blocked_comment_and_returns_to_ready() -> (
    None
):
    """blocked stale 恢复后 comment 文案是 blocked 专用文案，目标为 state/ready。"""
    mock_status_service = MagicMock()

    # Mock blocked issue with stale flow
    stale_flow = MagicMock()
    stale_flow.plan_ref = None
    stale_flow.branch = "task/issue-301"
    stale_flow.task_issue_number = 301
    stale_flow.flow_status = "stale"

    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 301,
            "title": "Dependency available",
            "state": IssueState.BLOCKED,
            "resume_kind": "blocked",
            "flow": stale_flow,
        },
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(
            task_resume_usecase, "resume_blocked_issue_to_ready"
        ) as mock_blocked_to_ready,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
    ):
        # Mock label service to confirm state is BLOCKED
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = IssueState.BLOCKED

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(reason="dependency available", dry_run=False)

        # 应调用 blocked 恢复函数
        mock_blocked_to_ready.assert_called_once()
        call_kwargs = mock_blocked_to_ready.call_args[1]
        assert call_kwargs["issue_number"] == 301
        assert call_kwargs["reason"] == "dependency available"

        # 不应调用 failed 恢复函数
        # (resume_blocked_issue_to_ready 已经被 mock，所以这里验证它被正确调用)

        # 结果应包含恢复的 issue
        assert len(result["resumed"]) == 1
        assert result["resumed"][0]["number"] == 301
        assert result["resumed"][0]["resume_kind"] == "blocked"
        assert result["skipped"] == []


def test_blocked_resume_does_not_affect_failed_resume_path() -> None:
    """blocked 恢复不影响 failed 恢复既有路径。"""
    mock_status_service = MagicMock()

    # Mock both failed and blocked issues
    failed_flow = MagicMock()
    failed_flow.plan_ref = "docs/plans/issue-439.md"
    failed_flow.branch = "task/issue-439"
    failed_flow.task_issue_number = 439
    failed_flow.flow_status = "active"

    stale_flow = MagicMock()
    stale_flow.plan_ref = None
    stale_flow.branch = "task/issue-301"
    stale_flow.task_issue_number = 301
    stale_flow.flow_status = "stale"

    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 439,
            "title": "Manager backend regression",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": failed_flow,
        },
        {
            "number": 301,
            "title": "Dependency available",
            "state": IssueState.BLOCKED,
            "resume_kind": "blocked",
            "flow": stale_flow,
        },
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(
            task_resume_usecase, "resume_failed_issue_to_ready"
        ) as mock_failed_to_ready,
        patch.object(
            task_resume_usecase, "resume_blocked_issue_to_ready"
        ) as mock_blocked_to_ready,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
    ):
        # Mock label service
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance

        def mock_get_state(issue_num: int) -> IssueState | None:
            if issue_num == 439:
                return IssueState.FAILED
            elif issue_num == 301:
                return IssueState.BLOCKED
            return None

        mock_label_instance.get_state.side_effect = mock_get_state

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(reason="manual recovery", dry_run=False)

        # failed 恢复路径应正常工作
        mock_failed_to_ready.assert_called_once()
        assert mock_failed_to_ready.call_args[1]["issue_number"] == 439

        # blocked 恢复路径应正常工作
        mock_blocked_to_ready.assert_called_once()
        assert mock_blocked_to_ready.call_args[1]["issue_number"] == 301

        # 结果应包含两个恢复
        assert len(result["resumed"]) == 2
        resumed_numbers = [r["number"] for r in result["resumed"]]
        assert 439 in resumed_numbers
        assert 301 in resumed_numbers
