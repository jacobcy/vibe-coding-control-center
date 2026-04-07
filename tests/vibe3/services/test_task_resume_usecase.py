"""Tests for TaskResumeUsecase."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.handoff_read import _get_live_sessions_for_branch
from vibe3.models.orchestration import IssueState
from vibe3.services import task_resume_operations, task_resume_usecase


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

        assert "candidates" in result
        assert len(result["candidates"]) == 2
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
            task_resume_operations, "resume_failed_issue_to_ready"
        ) as mock_failed_to_ready,
        patch.object(
            task_resume_operations, "resume_blocked_issue_to_ready"
        ) as mock_blocked_to_ready,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
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

        assert mock_failed_to_ready.call_count == 2
        failed_calls = [
            call.kwargs["issue_number"] for call in mock_failed_to_ready.call_args_list
        ]
        assert failed_calls == [439, 441]

        mock_blocked_to_ready.assert_called_once()
        assert mock_blocked_to_ready.call_args[1]["issue_number"] == 301

        assert mock_git_instance.remove_worktree.call_count == 3
        reactivated = [
            call.args[0] for call in mock_flow_instance.reactivate_flow.call_args_list
        ]
        assert reactivated == [
            mock_status_service.fetch_resume_candidates.return_value[0]["flow"].branch,
            mock_status_service.fetch_resume_candidates.return_value[1]["flow"].branch,
            mock_status_service.fetch_resume_candidates.return_value[2]["flow"].branch,
        ]
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
            task_resume_operations, "resume_failed_issue_to_ready"
        ) as mock_failed_to_ready,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
    ):
        mock_label_instance = MagicMock()
        mock_label_service.return_value = mock_label_instance
        mock_label_instance.get_state.return_value = IssueState.READY

        usecase = task_resume_usecase.TaskResumeUsecase()
        result = usecase.resume_issues(dry_run=False)

        mock_failed_to_ready.assert_not_called()
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["number"] == 439
        assert "不再处于" in result["skipped"][0]["reason"]
        assert result["resumed"] == []


def test_resume_issues_with_explicit_issue_bypasses_orchestra_candidate_filter() -> (
    None
):
    """显式点名恢复时，不应因非 orchestra 候选而被拦截。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = []
    mock_label_service = MagicMock()
    mock_label_service.get_state.return_value = IssueState.FAILED

    with patch.object(
        task_resume_operations,
        "resume_failed_issue_to_ready",
    ) as mock_failed_to_ready:
        usecase = task_resume_usecase.TaskResumeUsecase(
            status_service=mock_status_service,
            label_service=mock_label_service,
            flow_service=MagicMock(),
            git_client=MagicMock(),
            github_client=MagicMock(),
            issue_flow_service=MagicMock(),
        )

        result = usecase.resume_issues(
            issue_numbers=[320],
            dry_run=False,
            flows=[],
            stale_flows=[],
        )

        assert result["resumed"] == [{"number": 320, "resume_kind": "failed"}]
        assert result["skipped"] == []
        mock_failed_to_ready.assert_called_once_with(
            issue_number=320,
            repo=None,
            reason="",
        )


def test_resume_issues_with_explicit_issue_prefers_active_flow_scene() -> None:
    """显式点名恢复时，active flow 应优先于 stale flow。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = []
    mock_label_service = MagicMock()
    mock_label_service.get_state.return_value = IssueState.FAILED
    mock_git_client = MagicMock()
    mock_git_client.find_worktree_path_for_branch.return_value = "/tmp/task-320"
    mock_flow_service = MagicMock()
    mock_issue_flow_service = MagicMock()
    mock_issue_flow_service.is_task_branch.return_value = True
    active_flow = MagicMock(
        branch="task/issue-320",
        task_issue_number=320,
        flow_status="active",
        plan_ref=None,
    )
    stale_flow = MagicMock(
        branch="task/issue-320-stale",
        task_issue_number=320,
        flow_status="stale",
        plan_ref=None,
    )

    with patch.object(
        task_resume_operations,
        "resume_failed_issue_to_ready",
    ) as mock_failed_to_ready:
        usecase = task_resume_usecase.TaskResumeUsecase(
            status_service=mock_status_service,
            label_service=mock_label_service,
            flow_service=mock_flow_service,
            git_client=mock_git_client,
            github_client=MagicMock(),
            issue_flow_service=mock_issue_flow_service,
        )

        result = usecase.resume_issues(
            issue_numbers=[320],
            dry_run=False,
            flows=[active_flow],
            stale_flows=[stale_flow],
        )

        assert result["resumed"] == [{"number": 320, "resume_kind": "failed"}]
        mock_failed_to_ready.assert_called_once_with(
            issue_number=320,
            repo=None,
            reason="",
        )
        mock_git_client.find_worktree_path_for_branch.assert_called_once_with(
            "task/issue-320"
        )
        mock_flow_service.reactivate_flow.assert_called_once_with("task/issue-320")


def test_resume_issues_with_explicit_issue_can_reactivate_aborted_flow() -> None:
    """显式点名恢复时，aborted flow 也应绕过治理候选过滤。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = []
    mock_label_service = MagicMock()
    mock_label_service.get_state.return_value = IssueState.READY
    mock_flow_service = MagicMock()
    mock_issue_flow_service = MagicMock()
    mock_issue_flow_service.is_task_branch.return_value = False
    aborted_flow = MagicMock(
        branch="debug/issue-123",
        task_issue_number=123,
        flow_status="aborted",
    )
    mock_flow_service.list_flows.return_value = [aborted_flow]

    usecase = task_resume_usecase.TaskResumeUsecase(
        status_service=mock_status_service,
        label_service=mock_label_service,
        flow_service=mock_flow_service,
        git_client=MagicMock(),
        github_client=MagicMock(),
        issue_flow_service=mock_issue_flow_service,
    )

    result = usecase.resume_issues(
        issue_numbers=[123],
        dry_run=False,
        flows=[],
        stale_flows=[],
    )

    assert result["resumed"] == [{"number": 123, "resume_kind": "aborted"}]
    assert result["skipped"] == []
    mock_flow_service.reactivate_flow.assert_called_once_with("debug/issue-123")


def test_resume_issues_with_explicit_issue_prefers_aborted_flow_over_stale_task() -> (
    None
):
    """READY/HANDOFF 显式恢复时应优先选 aborted flow，而不是 stale task flow。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = []
    mock_label_service = MagicMock()
    mock_label_service.get_state.return_value = IssueState.READY
    mock_flow_service = MagicMock()
    mock_issue_flow_service = MagicMock()
    mock_issue_flow_service.is_task_branch.side_effect = (
        lambda branch: branch.startswith("task/")
    )
    stale_task_flow = MagicMock(
        branch="task/issue-123-stale",
        task_issue_number=123,
        flow_status="stale",
    )
    aborted_manual_flow = MagicMock(
        branch="debug/issue-123",
        task_issue_number=123,
        flow_status="aborted",
    )
    mock_flow_service.list_flows.return_value = [stale_task_flow, aborted_manual_flow]

    usecase = task_resume_usecase.TaskResumeUsecase(
        status_service=mock_status_service,
        label_service=mock_label_service,
        flow_service=mock_flow_service,
        git_client=MagicMock(),
        github_client=MagicMock(),
        issue_flow_service=mock_issue_flow_service,
    )

    result = usecase.resume_issues(
        issue_numbers=[123],
        dry_run=False,
        flows=[],
        stale_flows=[stale_task_flow],
    )

    assert result["resumed"] == [{"number": 123, "resume_kind": "aborted"}]
    assert result["skipped"] == []
    mock_flow_service.reactivate_flow.assert_called_once_with("debug/issue-123")


def test_resume_issues_marks_aborted_reactivation_failure_as_skipped() -> None:
    """aborted flow 重激活失败时，不应误报为 resumed。"""
    mock_status_service = MagicMock()
    mock_status_service.fetch_resume_candidates.return_value = []
    mock_label_service = MagicMock()
    mock_label_service.get_state.return_value = IssueState.READY
    mock_flow_service = MagicMock()
    mock_issue_flow_service = MagicMock()
    mock_issue_flow_service.is_task_branch.return_value = False
    aborted_flow = MagicMock(
        branch="debug/issue-123",
        task_issue_number=123,
        flow_status="aborted",
    )
    mock_flow_service.list_flows.return_value = [aborted_flow]
    mock_flow_service.reactivate_flow.side_effect = RuntimeError("boom")

    usecase = task_resume_usecase.TaskResumeUsecase(
        status_service=mock_status_service,
        label_service=mock_label_service,
        flow_service=mock_flow_service,
        git_client=MagicMock(),
        github_client=MagicMock(),
        issue_flow_service=mock_issue_flow_service,
    )

    result = usecase.resume_issues(
        issue_numbers=[123],
        dry_run=False,
        flows=[],
        stale_flows=[],
    )

    assert result["resumed"] == []
    assert result["skipped"] == [{"number": 123, "reason": "恢复操作失败"}]


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
            task_resume_operations, "resume_failed_issue_to_ready"
        ) as mock_failed_to_ready,
        patch.object(task_resume_usecase, "LabelService") as mock_label_service,
        patch.object(task_resume_usecase, "GitClient") as mock_git_client,
        patch.object(task_resume_usecase, "FlowService") as mock_flow_service,
        patch.object(
            task_resume_usecase, "IssueFlowService"
        ) as mock_issue_flow_service,
        patch("vibe3.services.task_resume_operations.subprocess.run") as mock_run,
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


def test_handoff_read_includes_runtime_sessions_from_registry(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """handoff read 结果中包含来自 registry 的 runtime_sessions 视图。

    _get_live_sessions_for_branch 应从 SQLite registry 读取 live sessions，
    按 branch 过滤后返回。
    """
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    # 在 registry 中创建一个 manager session（branch 匹配）
    store.create_runtime_session(
        role="manager",
        target_type="issue",
        target_id="451",
        branch="task/issue-451",
        session_name="vibe3-manager-issue-451",
        status="running",
    )
    # 另一个 branch 的 session（不应出现）
    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="999",
        branch="task/issue-999",
        session_name="vibe3-executor-issue-999",
        status="running",
    )

    sessions = _get_live_sessions_for_branch(store, "task/issue-451")

    assert len(sessions) == 1
    assert sessions[0]["role"] == "manager"
    assert sessions[0]["branch"] == "task/issue-451"
