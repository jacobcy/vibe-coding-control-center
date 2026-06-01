"""Tests for explicit flow rebuild usecase."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.flow_rebuild_usecase import FlowRebuildUsecase


def test_rebuild_issue_flow_hard_deletes_bootstraps_handoff_and_label_resume() -> None:
    store = MagicMock()
    git = MagicMock()
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
        patch("vibe3.services.flow_rebuild_usecase.FlowCleanupService") as cleanup_cls,
        patch("vibe3.services.flow_rebuild_usecase.HandoffService") as handoff_cls,
    ):
        cleanup = cleanup_cls.return_value
        cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        handoff = handoff_cls.return_value

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
    handoff.append_current_handoff.assert_called_once()
    label_resume.assert_called_once_with(
        issue_number=303,
        branch="task/issue-303",
        reason="missing worktree",
    )
    assert result == {"branch": "task/issue-303"}
