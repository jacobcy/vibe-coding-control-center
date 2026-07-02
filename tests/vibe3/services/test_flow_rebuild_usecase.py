"""Tests for explicit flow rebuild usecase."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.flow.rebuild import FlowRebuildUsecase


def test_rebuild_issue_flow_hard_deletes_bootstraps_handoff_and_label_resume(
    tmp_path: Path,
) -> None:
    worktree_path = tmp_path / "repo" / ".worktrees" / "task" / "issue-303"
    worktree_path.mkdir(parents=True)
    store = MagicMock()
    git = MagicMock()
    git.branch_exists.return_value = True
    git.find_worktree_path_for_branch.return_value = worktree_path
    github = MagicMock()
    orchestrator = MagicMock()
    orchestrator.bootstrap_issue_flow.return_value = {"branch": "task/issue-303"}
    label_resume = MagicMock()

    usecase = FlowRebuildUsecase(
        store=store,
        git_client=git,
        github_client=github,
        orchestrator=orchestrator,
        label_resume=label_resume,
    )

    issue = IssueInfo(
        number=303,
        title="Rebuild me",
        state=IssueState.READY,
        labels=[IssueState.READY.to_label()],
    )

    with (
        patch("vibe3.services.flow.rebuild.FlowCleanupService") as cleanup_cls,
        patch("vibe3.services.flow.timeline.FlowTimelineService") as timeline_cls,
        patch("vibe3.services.issue.flow.IssueFlowService") as issue_flow_cls,
    ):
        cleanup = cleanup_cls.return_value
        cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        issue_flow = issue_flow_cls.return_value
        issue_flow.resolve_task_issue_number.return_value = 303
        timeline = timeline_cls.return_value

        result = usecase.rebuild_issue_flow(
            issue=issue,
            branch="task/issue-303",
            reason="missing worktree",
            include_remote=True,
            ensure_worktree=True,
        )

    cleanup.cleanup_flow_scene.assert_called_once_with(
        "task/issue-303",
        include_remote=True,
        terminate_sessions=True,
        keep_flow_record=False,
        force_delete=True,
    )
    orchestrator.bootstrap_issue_flow.assert_called_once_with(
        issue,
        branch="task/issue-303",
        slug="issue-303",
        source="flow:rebuild",
        initiated_by="flow:rebuild",
        ensure_worktree=True,
        reactivate_existing=False,
    )
    timeline.record_timeline_event.assert_called_once_with(
        branch="task/issue-303",
        event_type="scene_rebuilt",
        actor="vibe3:flow_rebuild",
        detail="Scene rebuilt: missing worktree",
        issue_number=303,
    )
    store.reset_transition_epoch.assert_called_once_with("task/issue-303")
    label_resume.assert_called_once_with(
        issue_number=303,
        branch="task/issue-303",
        reason="missing worktree",
    )
    assert result == {"branch": "task/issue-303"}


def test_rebuild_issue_flow_fails_when_rebuilt_worktree_is_missing() -> None:
    store = MagicMock()
    git = MagicMock()
    git.branch_exists.return_value = True
    git.find_worktree_path_for_branch.return_value = None
    github = MagicMock()
    orchestrator = MagicMock()
    orchestrator.bootstrap_issue_flow.return_value = {
        "branch": "task/issue-303",
        "worktree_path": "/tmp/repo/.worktrees/task/issue-303",
    }
    label_resume = MagicMock()

    usecase = FlowRebuildUsecase(
        store=store,
        git_client=git,
        github_client=github,
        orchestrator=orchestrator,
        label_resume=label_resume,
    )

    issue = IssueInfo(
        number=303,
        title="Rebuild me",
        state=IssueState.READY,
        labels=[IssueState.READY.to_label()],
    )

    with (
        patch("vibe3.services.flow.rebuild.FlowCleanupService") as cleanup_cls,
        patch("vibe3.services.flow.timeline.FlowTimelineService") as timeline_cls,
        patch("vibe3.services.issue.flow.IssueFlowService"),
        pytest.raises(RuntimeError, match="Rebuild postcondition failed"),
    ):
        cleanup = cleanup_cls.return_value
        cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        usecase.rebuild_issue_flow(
            issue=issue,
            branch="task/issue-303",
            reason="missing worktree",
            include_remote=True,
            ensure_worktree=True,
        )

    timeline_cls.return_value.record_timeline_event.assert_not_called()
    label_resume.assert_not_called()
