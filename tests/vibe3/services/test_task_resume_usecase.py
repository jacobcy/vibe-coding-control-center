"""Tests for TaskResumeUsecase."""

import subprocess
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


def test_resume_issues_apply_routes_failed_by_plan_ref_and_blocked_to_ready() -> None:
    """failed/blocked 恢复都会清理 task worktree 并回到 ready。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 439,
            "title": "Manager backend regression",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": MagicMock(
                plan_ref="docs/plans/issue-439.md", branch="task/issue-439"
            ),
        },
        {
            "number": 441,
            "title": "API timeout",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": MagicMock(plan_ref=None, branch="task/issue-441"),
        },
        {
            "number": 301,
            "title": "Dependency available",
            "state": IssueState.BLOCKED,
            "resume_kind": "blocked",
            "flow": MagicMock(plan_ref=None, branch="task/issue-301"),
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
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
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
        mock_git_instance = MagicMock()
        mock_git_client.return_value = mock_git_instance
        mock_git_instance.find_worktree_path_for_branch.side_effect = [
            "/tmp/issue-439",
            "/tmp/issue-441",
            "/tmp/issue-301",
        ]
        mock_flow_instance = MagicMock()
        mock_flow_service.return_value = mock_flow_instance

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(dry_run=False)

        # failed 无论有无 plan_ref 都回到 ready
        assert mock_failed_to_ready.call_count == 2
        failed_calls = [
            call.kwargs["issue_number"] for call in mock_failed_to_ready.call_args_list
        ]
        assert failed_calls == [439, 441]

        # 301: blocked -> ready
        mock_blocked_to_ready.assert_called_once()
        assert mock_blocked_to_ready.call_args[1]["issue_number"] == 301

        # task worktree 应被删除，flow 应被重新激活清空 refs/session
        assert mock_git_instance.remove_worktree.call_count == 3
        reactivated = [
            call.args[0] for call in mock_flow_instance.reactivate_flow.call_args_list
        ]
        assert reactivated == [
            mock_status_service.fetch_resume_candidates.return_value[0]["flow"].branch,
            mock_status_service.fetch_resume_candidates.return_value[1]["flow"].branch,
            mock_status_service.fetch_resume_candidates.return_value[2]["flow"].branch,
        ]

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
            task_resume_usecase, "resume_failed_issue_to_ready"
        ) as mock_failed_to_ready,
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
        mock_failed_to_ready.assert_not_called()

        # 应被跳过
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["number"] == 439
        # skipped reason 要明确说明是"不再处于 failed/blocked 状态"
        assert "不再处于" in result["skipped"][0]["reason"]
        assert result["resumed"] == []


def test_resume_issues_with_empty_issue_list_does_not_fall_back_to_all_candidates() -> (
    None
):
    """显式传入空 issue 列表时，不应退化成恢复所有候选。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 301,
            "title": "Dependency available",
            "state": IssueState.BLOCKED,
            "resume_kind": "blocked",
            "flow": MagicMock(branch="task/issue-301"),
        },
    ]

    with patch.object(
        task_resume_usecase, "StatusQueryService", return_value=mock_status_service
    ):
        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(issue_numbers=[], dry_run=True)

        assert result["candidates"] == []
        assert result["requested"] == []
        assert result["resumed"] == []
        assert result["skipped"] == []


def test_resume_issues_clears_existing_tmux_sessions_before_reactivate() -> None:
    """恢复 task scene 前应先清理 issue 对应的旧 tmux session。"""
    mock_status_service = MagicMock()
    flow = MagicMock(
        branch="task/issue-320",
        plan_ref=None,
        manager_session_id="stale-backend-session",
        planner_session_id=None,
        executor_session_id=None,
        reviewer_session_id=None,
    )
    mock_status_service.fetch_resume_candidates.return_value = [
        {
            "number": 320,
            "title": "Manager backend regression",
            "state": IssueState.FAILED,
            "resume_kind": "failed",
            "flow": flow,
        },
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(
            task_resume_usecase, "resume_failed_issue_to_ready"
        ) as mock_failed_to_ready,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
        patch.object(
            task_resume_usecase, "IssueFlowService"
        ) as mock_issue_flow_service,
        patch("vibe3.services.task_resume_usecase.subprocess.run") as mock_run,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = IssueState.FAILED
        mock_git_instance = MagicMock()
        mock_git_client.return_value = mock_git_instance
        mock_git_instance.find_worktree_path_for_branch.return_value = None
        mock_flow_instance = MagicMock()
        mock_flow_service.return_value = mock_flow_instance
        mock_issue_flow_service.return_value.parse_issue_number.return_value = 320
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=["tmux", "ls"],
                returncode=0,
                stdout=(
                    "vibe3-manager-issue-320: 1 windows\n"
                    "vibe3-manager-issue-320-2: 1 windows\n"
                    "vibe3-plan-issue-320: 1 windows\n"
                ),
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["tmux", "kill-session", "-t", "vibe3-manager-issue-320"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["tmux", "kill-session", "-t", "vibe3-manager-issue-320-2"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["tmux", "kill-session", "-t", "vibe3-plan-issue-320"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ]

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(dry_run=False)

        assert result["resumed"] == [{"number": 320, "resume_kind": "failed"}]
        mock_failed_to_ready.assert_called_once()
        mock_flow_instance.reactivate_flow.assert_called_once_with("task/issue-320")
        kill_calls = [call.args[0] for call in mock_run.call_args_list[1:]]
        assert kill_calls == [
            ["tmux", "kill-session", "-t", "vibe3-manager-issue-320"],
            ["tmux", "kill-session", "-t", "vibe3-manager-issue-320-2"],
            ["tmux", "kill-session", "-t", "vibe3-plan-issue-320"],
        ]
