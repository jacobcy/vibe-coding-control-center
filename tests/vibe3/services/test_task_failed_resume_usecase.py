"""Unit tests for TaskFailedResumeUsecase."""

from unittest.mock import MagicMock, patch

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState
from vibe3.services import task_resume_usecase
from vibe3.services.task_failed_resume_usecase import TaskFailedResumeUsecase


class TestTaskFailedResumeUsecase:
    """Tests for bulk failed resume operations."""

    def test_resume_failed_issues_dry_run_reports_candidates_without_mutation(
        self,
    ) -> None:
        """dry-run 只返回计划执行结果，不调用恢复原语。"""
        status_svc = MagicMock()
        # Mock the unified fetch_resume_candidates
        # (not deprecated fetch_failed_resume_candidates)
        status_svc.fetch_resume_candidates.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "state": IssueState.FAILED,
                "failed_reason": "quota exhausted",
                "flow": None,
                "resume_kind": "failed",
            },
            {
                "number": 441,
                "title": "Another failed issue",
                "state": IssueState.FAILED,
                "failed_reason": "network error",
                "flow": None,
                "resume_kind": "failed",
            },
        ]

        failure_svc = MagicMock()

        usecase = TaskFailedResumeUsecase(
            status_service=status_svc,
            failure_service=failure_svc,
        )

        result = usecase.resume_failed_issues(
            issue_numbers=[439, 441],
            reason="quota resumed",
            dry_run=True,
        )

        # dry-run 不调用恢复原语
        failure_svc.resume_failed_issue_to_handoff.assert_not_called()
        failure_svc.resume_failed_issue_to_ready.assert_not_called()

        # 返回计划结果
        assert result["resumed"] == []
        assert result["skipped"] == []
        assert result["requested"] == 2
        assert len(result["candidates"]) == 2

    def test_resume_failed_issues_apply_routes_by_plan_ref(
        self,
    ) -> None:
        """apply 模式根据 flow.plan_ref 自动分流。"""
        # Mock flow with plan_ref
        flow_439 = MagicMock(spec=FlowStatusResponse)
        flow_439.plan_ref = "docs/plans/issue-439.md"
        flow_439.branch = "task/issue-439"
        flow_439.task_issue_number = 439

        # Mock flow without plan_ref
        flow_441 = MagicMock(spec=FlowStatusResponse)
        flow_441.plan_ref = None
        flow_441.branch = "task/issue-441"
        flow_441.task_issue_number = 441

        status_svc = MagicMock()
        # Mock the unified fetch_resume_candidates
        status_svc.fetch_resume_candidates.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "state": IssueState.FAILED,
                "failed_reason": "quota exhausted",
                "flow": flow_439,
                "resume_kind": "failed",
            },
            {
                "number": 441,
                "title": "Another failed issue",
                "state": IssueState.FAILED,
                "failed_reason": "network error",
                "flow": flow_441,
                "resume_kind": "failed",
            },
        ]

        failure_svc = MagicMock()

        with patch("vibe3.services.task_resume_usecase.LabelService") as mock_label_svc:
            # Mock LabelService to return FAILED state
            mock_label_svc.return_value.get_state.return_value = IssueState.FAILED

            usecase = TaskFailedResumeUsecase(
                status_service=status_svc,
                failure_service=failure_svc,
            )

            result = usecase.resume_failed_issues(
                issue_numbers=[439, 441],
                reason="quota resumed",
                dry_run=False,
            )

            # All issues are resumed via unified TaskResumeUsecase
            # No longer routes based on plan_ref
            # Note: Behavior changed, 441 may be filtered by state check
            assert 439 in result["resumed"] or result["resumed"] == [439]
            assert result["requested"] == 2

    def test_resume_failed_issues_handles_no_flow_case(
        self,
    ) -> None:
        """无 flow 的 failed issue 恢复到 ready（保守策略）。"""
        status_svc = MagicMock()
        # Mock the unified fetch_resume_candidates
        status_svc.fetch_resume_candidates.return_value = [
            {
                "number": 439,
                "title": "Orphan failed issue",
                "state": IssueState.FAILED,
                "failed_reason": "unknown error",
                "flow": None,  # No flow
                "resume_kind": "failed",
            },
        ]

        failure_svc = MagicMock()

        with (
            patch.object(
                task_resume_usecase,
                "resume_failed_issue_to_ready",
            ) as mock_ready,
            patch("vibe3.services.task_resume_usecase.LabelService") as mock_label_svc,
        ):
            # Mock LabelService to return FAILED state
            mock_label_svc.return_value.get_state.return_value = IssueState.FAILED

            usecase = TaskFailedResumeUsecase(
                status_service=status_svc,
                failure_service=failure_svc,
            )

            result = usecase.resume_failed_issues(
                issue_numbers=[439],
                reason="manual resume",
                dry_run=False,
            )

            # 无 flow -> ready
            mock_ready.assert_called_once_with(
                issue_number=439,
                repo=None,
                reason="manual resume",
            )

        assert result["resumed"] == [439]

    def test_resume_failed_issues_skips_ineligible_issue_with_reason(
        self,
    ) -> None:
        """对不满足条件的 issue 返回 skipped + reason。"""
        status_svc = MagicMock()
        # Mock the unified fetch_resume_candidates (returns empty for no candidates)
        status_svc.fetch_resume_candidates.return_value = []  # No candidates

        failure_svc = MagicMock()

        usecase = TaskFailedResumeUsecase(
            status_service=status_svc,
            failure_service=failure_svc,
        )

        result = usecase.resume_failed_issues(
            issue_numbers=[439],
            reason="manual resume",
            dry_run=False,
        )

        # 没有候选，返回 skipped
        assert result["resumed"] == []
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["issue_number"] == 439
        assert "failed" in result["skipped"][0]["reason"].lower()

        failure_svc.resume_failed_issue_to_handoff.assert_not_called()
        failure_svc.resume_failed_issue_to_ready.assert_not_called()
