"""Tests for TaskResumeUsecase --all mode."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services import task_resume_usecase


def test_resume_issues_all_task_mode_resets_any_task_issue_to_ready() -> None:
    """--all 模式会重置所有 task/issue-* flow 到 ready，但不处理 do 分支。"""
    flow_340 = MagicMock(branch="task/issue-340", task_issue_number=340)
    flow_410 = MagicMock(branch="task/issue-410", task_issue_number=410)
    flow_do = MagicMock(branch="do/20260406-32b564", task_issue_number=None)

    mock_status_service = MagicMock()
    mock_status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 340,
            "title": "Reset claimed flow",
            "state": IssueState.CLAIMED,
            "flow": flow_340,
        },
        {
            "number": 410,
            "title": "Reset failed flow",
            "state": IssueState.FAILED,
            "flow": flow_410,
        },
        {
            "number": 999,
            "title": "Ignore do flow",
            "state": IssueState.IN_PROGRESS,
            "flow": flow_do,
        },
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
        patch.object(task_resume_usecase, "GitHubClient") as mock_github_client,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.side_effect = lambda num: {
            340: IssueState.CLAIMED,
            410: IssueState.FAILED,
        }.get(num)
        mock_git_instance = MagicMock()
        mock_git_client.return_value = mock_git_instance
        mock_git_instance.find_worktree_path_for_branch.side_effect = [
            "/tmp/issue-340",
            "/tmp/issue-410",
        ]
        mock_flow_instance = MagicMock()
        mock_flow_service.return_value = mock_flow_instance
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(
            dry_run=False,
            candidate_mode="all_task",
            flows=[flow_340, flow_410, flow_do],
        )

        assert [item["number"] for item in result["resumed"]] == [340, 410]
        assert result["requested"] == [340, 410]
        assert mock_git_instance.remove_worktree.call_count == 2
        reactivated = [
            call.args[0] for call in mock_flow_instance.reactivate_flow.call_args_list
        ]
        assert reactivated == ["task/issue-340", "task/issue-410"]
        confirmed = [
            call.args[1]
            for call in mock_label_instance.confirm_issue_state.call_args_list
        ]
        assert confirmed == [IssueState.READY, IssueState.READY]


def test_resume_issues_all_task_mode_skips_duplicate_comment_when_reason_empty() -> (
    None
):
    """--all 且空 reason 时，如 comment 已存在则不重复发。"""
    flow_340 = MagicMock(branch="task/issue-340", task_issue_number=340)

    mock_status_service = MagicMock()
    mock_status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 340,
            "title": "Reset claimed flow",
            "state": IssueState.CLAIMED,
            "flow": flow_340,
        }
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
        patch.object(task_resume_usecase, "GitHubClient") as mock_github_client,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = IssueState.CLAIMED
        mock_git_instance = MagicMock()
        mock_git_client.return_value = mock_git_instance
        mock_git_instance.find_worktree_path_for_branch.return_value = "/tmp/issue-340"
        mock_flow_instance = MagicMock()
        mock_flow_service.return_value = mock_flow_instance
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance
        mock_github_instance.view_issue.return_value = {
            "comments": [
                {
                    "body": "[resume] 已重置 task scene，回到 state/ready。\n\n"
                    "后续会按标准 dispatcher/manager 路径重新创建 worktree 并执行。"
                }
            ]
        }

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(
            dry_run=False,
            candidate_mode="all_task",
            flows=[flow_340],
            reason="",
        )

        assert [item["number"] for item in result["resumed"]] == [340]
        mock_github_instance.add_comment.assert_not_called()


def test_resume_issues_all_task_mode_does_not_skip_when_duplicate_is_not_latest() -> (
    None
):
    """--all 只压掉相邻重复 comment，历史旧 comment 不应阻止新的恢复记录。"""
    flow_340 = MagicMock(branch="task/issue-340", task_issue_number=340)

    mock_status_service = MagicMock()
    mock_status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 340,
            "title": "Reset claimed flow",
            "state": IssueState.CLAIMED,
            "flow": flow_340,
        }
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
        patch.object(task_resume_usecase, "GitHubClient") as mock_github_client,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = IssueState.CLAIMED
        mock_git_instance = MagicMock()
        mock_git_client.return_value = mock_git_instance
        mock_git_instance.find_worktree_path_for_branch.return_value = "/tmp/issue-340"
        mock_flow_instance = MagicMock()
        mock_flow_service.return_value = mock_flow_instance
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance
        mock_github_instance.view_issue.return_value = {
            "comments": [
                {
                    "body": "[resume] 已重置 task scene，回到 state/ready。\n\n"
                    "后续会按标准 dispatcher/manager 路径重新创建 worktree 并执行。"
                },
                {"body": "some newer unrelated comment"},
            ]
        }

        usecase = task_resume_usecase.TaskResumeUsecase()
        usecase.resume_issues(
            dry_run=False,
            candidate_mode="all_task",
            flows=[flow_340],
            reason="",
        )

        mock_github_instance.add_comment.assert_called_once()


def test_resume_issues_all_task_mode_resets_scene_without_state_label() -> None:
    """--all 不应因 issue 缺少 orchestration state label 而跳过 scene 重置。"""
    flow_409 = MagicMock(branch="task/issue-409", task_issue_number=409)

    mock_status_service = MagicMock()
    mock_status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 409,
            "title": "Reset orphaned task scene",
            "state": None,
            "flow": flow_409,
        }
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
        patch.object(task_resume_usecase, "GitHubClient") as mock_github_client,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = None
        mock_git_instance = MagicMock()
        mock_git_client.return_value = mock_git_instance
        mock_git_instance.find_worktree_path_for_branch.return_value = "/tmp/issue-409"
        mock_flow_instance = MagicMock()
        mock_flow_service.return_value = mock_flow_instance
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance
        mock_github_instance.view_issue.return_value = {"comments": []}

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(
            dry_run=False,
            candidate_mode="all_task",
            flows=[flow_409],
            reason="",
        )

        assert [item["number"] for item in result["resumed"]] == [409]
        assert result["skipped"] == []
        mock_git_instance.remove_worktree.assert_called_once_with(
            "/tmp/issue-409", force=True
        )
        mock_flow_instance.reactivate_flow.assert_called_once_with("task/issue-409")


def test_resume_issues_all_task_mode_skips_ready_scene_without_worktree() -> None:
    """--all 遇到已是 ready 且无 worktree 的 scene 应直接跳过。"""
    flow_415 = MagicMock(
        branch="task/issue-415",
        task_issue_number=415,
        manager_session_id=None,
        planner_session_id=None,
        executor_session_id=None,
        reviewer_session_id=None,
    )

    mock_status_service = MagicMock()
    mock_status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 415,
            "title": "Already ready without task scene",
            "state": IssueState.READY,
            "flow": flow_415,
        }
    ]

    with (
        patch.object(
            task_resume_usecase, "StatusQueryService", return_value=mock_status_service
        ),
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
        patch.object(task_resume_usecase, "GitHubClient") as mock_github_client,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = IssueState.READY
        mock_git_instance = MagicMock()
        mock_git_client.return_value = mock_git_instance
        mock_git_instance.find_worktree_path_for_branch.return_value = None
        mock_flow_instance = MagicMock()
        mock_flow_service.return_value = mock_flow_instance
        mock_github_instance = MagicMock()
        mock_github_client.return_value = mock_github_instance

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(
            dry_run=False,
            candidate_mode="all_task",
            flows=[flow_415],
            reason="",
        )

        assert result["resumed"] == []
        assert result["skipped"] == [
            {"number": 415, "reason": "已是 state/ready 且无 task scene，跳过恢复"}
        ]
        mock_git_instance.remove_worktree.assert_not_called()
        mock_flow_instance.reactivate_flow.assert_not_called()
