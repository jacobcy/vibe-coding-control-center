from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import GitError
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.flow.cleanup import (
    FlowCleanupService,
    LiveSessionsDetectedError,
)


def test_terminate_task_sessions_raises_when_live_sessions_exist() -> None:
    backend = MagicMock()
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
        backend=backend,
    )
    service.issue_flow_service.parse_issue_number.return_value = 123

    with patch(
        "vibe3.environment.session_registry.SessionRegistryService"
    ) as registry_cls:
        registry_cls.return_value.get_truly_live_sessions_for_branch.return_value = [
            {"session_id": "vibe3-run-issue-123"}
        ]

        with pytest.raises(LiveSessionsDetectedError, match="live sessions found"):
            service._terminate_task_sessions("task/issue-123")
        registry_cls.assert_called_once_with(store=service.store, backend=backend)


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

    with patch("vibe3.clients.git_worktree_ops.prune_worktrees") as mock_prune:
        results: dict[str, bool] = {"worktree": True}
        service._remove_worktree("task/issue-123", results)

        # Prune must be called as fallback
        mock_prune.assert_called_once()
        # Worktree step should still be marked as failed
        assert results["worktree"] is False


def test_is_cleanup_commit_matches_init() -> None:
    """_is_cleanup_commit returns True for 'init' commit subjects."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )

    assert service._is_cleanup_commit("init") is True
    assert service._is_cleanup_commit("Init") is True  # case-insensitive
    assert service._is_cleanup_commit("INIT") is True  # case-insensitive


def test_is_cleanup_commit_rejects_real_commit() -> None:
    """_is_cleanup_commit returns False for real commit subjects."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )

    assert service._is_cleanup_commit("fix: typo") is False
    assert service._is_cleanup_commit("feat: add new feature") is False
    assert service._is_cleanup_commit("refactor: simplify logic") is False
    assert service._is_cleanup_commit("initial commit") is False  # not exact match
    assert service._is_cleanup_commit("") is False


def test_has_meaningful_commits_returns_false_for_only_init_commits() -> None:
    """_has_meaningful_commits returns False when branch only has 'init' commits."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )

    # Mock git client to return only init commits
    service.git_client.get_commit_subjects.return_value = ["init", "init"]

    result = service._has_meaningful_commits("task/issue-123")

    assert result is False
    service.git_client.get_commit_subjects.assert_called_once_with(
        base_ref="origin/main", head_ref="task/issue-123"
    )


def test_has_meaningful_commits_returns_true_for_mixed_commits() -> None:
    """_has_meaningful_commits returns True when branch has real commits."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )

    # Mock git client to return init + real commits
    service.git_client.get_commit_subjects.return_value = [
        "init",
        "fix: real change",
    ]

    result = service._has_meaningful_commits("task/issue-123")

    assert result is True


def test_has_meaningful_commits_returns_true_for_only_real_commits() -> None:
    """_has_meaningful_commits returns True when branch has only real commits."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )

    # Mock git client to return only real commits
    service.git_client.get_commit_subjects.return_value = [
        "feat: add feature",
        "fix: bug fix",
    ]

    result = service._has_meaningful_commits("task/issue-123")

    assert result is True


def test_has_meaningful_commits_returns_true_on_error() -> None:
    """_has_meaningful_commits returns True on error to avoid blocking cleanup."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )

    # Mock git client to raise exception
    service.git_client.get_commit_subjects.side_effect = Exception("git error")

    result = service._has_meaningful_commits("task/issue-123")

    # Should return True to avoid blocking legitimate cleanup
    assert result is True


def test_delete_remote_branch_skips_when_only_init_commits() -> None:
    """Remote branch deletion must be skipped when branch only has init commits."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )
    service.git_client.delete_remote_branch = MagicMock()
    service._pr_service = MagicMock()

    results = {"remote_branch": True}

    with (
        patch.object(service, "_has_remote_branch", return_value=True),
        patch.object(service, "_has_meaningful_commits", return_value=False),
    ):
        service._delete_remote_branch("task/issue-123", results)

    # delete_remote_branch should NOT be called
    service.git_client.delete_remote_branch.assert_not_called()
    # Results should remain True (successful skip)
    assert results["remote_branch"] is True


def test_delete_remote_branch_proceeds_when_meaningful_commits_exist() -> None:
    """Remote branch deletion proceeds when branch has meaningful commits."""
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )
    service.git_client.delete_remote_branch = MagicMock()
    service._pr_service = MagicMock()
    service._pr_service.get_open_pr_for_branch.return_value = None

    results = {"remote_branch": True}

    with (
        patch.object(service, "_has_remote_branch", return_value=True),
        patch.object(service, "_has_meaningful_commits", return_value=True),
    ):
        service._delete_remote_branch("task/issue-456", results)

    # delete_remote_branch should be called
    service.git_client.delete_remote_branch.assert_called_once_with("task/issue-456")
    assert results["remote_branch"] is True
