# tests/vibe3/manager/test_manager_run_service.py
from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState


def test_run_manager_reads_backend_from_env(monkeypatch):
    """VIBE3_MANAGER_BACKEND/MODEL env vars should override config resolution."""
    monkeypatch.setenv("VIBE3_MANAGER_BACKEND", "gemini")
    monkeypatch.setenv("VIBE3_MANAGER_MODEL", "gemini-3-flash-preview")

    captured_options = {}

    def fake_resolve_manager_agent_options(config, runtime_config):
        # This should NOT be called when env vars are set
        captured_options["called"] = True
        return MagicMock(backend="wrong-backend", model="wrong-model")

    with (
        patch(
            "vibe3.runtime.agent_resolver.resolve_manager_agent_options",
            side_effect=fake_resolve_manager_agent_options,
        ),
        patch("vibe3.manager.manager_run_service.OrchestraConfig") as mock_config,
        patch("vibe3.manager.manager_run_service.GitHubClient") as mock_gh,
        patch("vibe3.manager.manager_run_service.SQLiteClient"),
        patch("vibe3.manager.manager_run_service.GitClient"),
        patch("vibe3.manager.manager_run_service.CodeagentBackend") as mock_backend,
    ):

        mock_config.from_settings.return_value = MagicMock(repo=None)
        mock_gh.return_value.view_issue.return_value = {
            "number": 301,
            "title": "test",
            "labels": [],
            "state": "open",
        }
        mock_backend_instance = MagicMock()
        mock_backend.return_value = mock_backend_instance
        mock_backend_instance.start_async.return_value = MagicMock(
            tmux_session="test-session", log_path="/tmp/test.log"
        )

        from vibe3.manager.manager_run_service import run_manager_issue_mode

        try:
            run_manager_issue_mode(
                issue_number=301,
                dry_run=False,
                async_mode=True,
            )
        except Exception:
            pass

    # resolve_manager_agent_options should NOT have been called
    assert not captured_options.get(
        "called"
    ), "resolve_manager_agent_options was called even though env vars were set"


@patch("vibe3.environment.worktree.WorktreeManager")
def test_resolve_manager_execution_cwd_marks_worktree_when_resolved(
    mock_manager, tmp_path
):
    """When WorktreeManager returns a dedicated cwd, worktree flag should be True."""
    mock_manager.return_value.resolve_manager_cwd.return_value = (tmp_path, True)

    from vibe3.manager.manager_run_service import resolve_manager_execution_cwd

    cwd = resolve_manager_execution_cwd(
        orchestra_config=MagicMock(),
        issue_number=42,
        target_branch="task/issue-42",
        current_branch="main",
        session_id=None,
    )

    assert cwd == tmp_path
    mock_manager.return_value.resolve_manager_cwd.assert_called_once_with(
        42, "task/issue-42"
    )


@patch("vibe3.manager.manager_run_service.resolve_manager_launch_cwd")
@patch("vibe3.environment.worktree.WorktreeManager")
def test_resolve_manager_execution_cwd_falls_back_without_worktree(
    mock_manager, mock_launch
):
    """If WorktreeManager cannot resolve, fall back without worktree flag."""
    mock_manager.return_value.resolve_manager_cwd.return_value = (None, False)
    mock_launch.return_value = MagicMock()

    from vibe3.manager.manager_run_service import resolve_manager_execution_cwd

    cwd = resolve_manager_execution_cwd(
        orchestra_config=MagicMock(),
        issue_number=99,
        target_branch="feature/99",
        current_branch="main",
        session_id=None,
    )

    assert cwd == mock_launch.return_value
    mock_launch.assert_called_once()


@patch("vibe3.manager.manager_run_coordinator.AbandonFlowService")
def test_handle_closed_issue_finalizes_abandon_for_handoff(mock_abandon_service):
    """Closed HANDOFF issue should finalize PR close + flow abort.

    Uses abandon service for cleanup.
    """
    from vibe3.manager.manager_run_coordinator import ManagerRunCoordinator

    store = MagicMock()
    coordinator = ManagerRunCoordinator(store=store)
    actor = "agent:manager"
    before_snapshot = {
        "state_label": "state/handoff",
        "issue_state": "open",
        "flow_status": "active",
    }
    after_snapshot = {
        "state_label": "state/handoff",
        "issue_state": "closed",
        "flow_status": "active",
    }

    handled = coordinator.handle_post_run_outcome(
        issue_number=123,
        branch="task/issue-123",
        actor=actor,
        repo="jacobcy/vibe-coding-control-center",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )

    assert handled is True
    mock_abandon_service.return_value.abandon_flow.assert_called_once_with(
        issue_number=123,
        branch="task/issue-123",
        source_state=IssueState.HANDOFF,
        reason="manager closed issue without finalizing abandon flow",
        actor=actor,
        issue_already_closed=True,
        flow_already_aborted=False,
    )


@patch("vibe3.manager.manager_run_coordinator.block_manager_noop_issue")
@patch("vibe3.manager.manager_run_coordinator.AbandonFlowService")
def test_handle_closed_issue_retries_cleanup_when_flow_already_aborted(
    mock_abandon_service, mock_block_noop
):
    """Closed issue with aborted flow should still retry PR cleanup.

    Uses abandon service even when flow is already aborted.
    """
    from vibe3.manager.manager_run_coordinator import ManagerRunCoordinator

    store = MagicMock()
    coordinator = ManagerRunCoordinator(store=store)
    handled = coordinator.handle_post_run_outcome(
        issue_number=123,
        branch="task/issue-123",
        actor="agent:manager",
        repo="jacobcy/vibe-coding-control-center",
        before_snapshot={
            "state_label": "state/ready",
            "issue_state": "open",
            "flow_status": "active",
        },
        after_snapshot={
            "state_label": "state/ready",
            "issue_state": "closed",
            "flow_status": "aborted",
        },
    )

    assert handled is True
    mock_abandon_service.return_value.abandon_flow.assert_called_once_with(
        issue_number=123,
        branch="task/issue-123",
        source_state=IssueState.READY,
        reason="manager closed issue without finalizing abandon flow",
        actor="agent:manager",
        issue_already_closed=True,
        flow_already_aborted=True,
    )
    mock_block_noop.assert_not_called()
