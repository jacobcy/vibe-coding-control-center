from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import GitError
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.flow_cleanup_service import (
    FlowCleanupService,
    LiveSessionsDetectedError,
)


def test_terminate_task_sessions_raises_when_live_sessions_exist() -> None:
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )
    service.issue_flow_service.parse_issue_number.return_value = 123

    with (
        patch("vibe3.agents.backends.codeagent.CodeagentBackend") as backend_cls,
        patch("vibe3.environment.session_registry.SessionRegistryService") as registry,
    ):
        registry.return_value.get_truly_live_sessions_for_branch.return_value = [
            {"session_id": "vibe3-run-issue-123"}
        ]

        with pytest.raises(LiveSessionsDetectedError, match="live sessions found"):
            service._terminate_task_sessions("task/issue-123")
        backend_cls.assert_called_once_with()


def test_cleanup_flow_scene_aborts_when_live_sessions_exist() -> None:
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )
    service.issue_flow_service.is_task_branch.return_value = True

    with (
        patch.object(
            service,
            "_terminate_task_sessions",
            side_effect=LiveSessionsDetectedError("live sessions found"),
        ),
        patch.object(service, "_remove_worktree") as remove_worktree,
        patch.object(service, "_delete_local_branch") as delete_local_branch,
        patch.object(service, "_delete_remote_branch") as delete_remote_branch,
        patch.object(service, "_clear_handoff") as clear_handoff,
        patch.object(service, "_handle_flow_record") as handle_flow_record,
    ):
        with pytest.raises(LiveSessionsDetectedError, match="live sessions found"):
            service.cleanup_flow_scene("task/issue-123")

        remove_worktree.assert_not_called()
        delete_local_branch.assert_not_called()
        delete_remote_branch.assert_not_called()
        clear_handoff.assert_not_called()
        handle_flow_record.assert_not_called()


def test_delete_remote_branch_skips_when_open_pr_exists() -> None:
    """Remote branch deletion must be skipped when branch still has an open PR."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )
    service.git_client.delete_remote_branch = MagicMock()
    service._pr_service = MagicMock()

    open_pr = PRResponse(
        number=321,
        title="Keep remote branch",
        body="Body",
        state=PRState.OPEN,
        head_branch="task/issue-321",
        base_branch="main",
        url="https://github.com/test/pr/321",
        draft=False,
        is_ready=True,
        ci_passed=False,
        created_at=None,
        updated_at=None,
        merged_at=None,
        metadata=None,
    )

    results = {"remote_branch": True}

    with patch.object(service, "_has_remote_branch", return_value=True):
        service._pr_service.get_open_pr_for_branch.return_value = open_pr
        service._delete_remote_branch("task/issue-321", results)

    service.git_client.delete_remote_branch.assert_not_called()
    assert results["remote_branch"] is True


def test_remove_worktree_falls_back_to_prune_on_failure() -> None:
    """When remove_worktree raises GitError, _remove_worktree must try prune."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )

    # Simulate: find_worktree_path_for_branch returns a path,
    # but remove_worktree raises GitError (orphan metadata)
    service.git_client.find_worktree_path_for_branch.return_value = (
        "/tmp/stale-worktree"
    )
    service.git_client.remove_worktree.side_effect = GitError(
        "worktree remove", "fatal: validation failed"
    )

    with patch("vibe3.clients.prune_worktrees") as mock_prune:
        results: dict[str, bool] = {"worktree": True}
        service._remove_worktree("task/issue-123", results)

        # Prune must be called as fallback
        mock_prune.assert_called_once()
        # Worktree step should still be marked as failed
        assert results["worktree"] is False
