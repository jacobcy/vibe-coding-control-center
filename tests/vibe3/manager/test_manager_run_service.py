# tests/vibe3/manager/test_manager_run_service.py
from unittest.mock import MagicMock, patch


def test_run_manager_reads_backend_from_env(monkeypatch):
    """VIBE3_MANAGER_BACKEND/MODEL env vars should override config resolution."""
    monkeypatch.setenv("VIBE3_MANAGER_BACKEND", "gemini")
    monkeypatch.setenv("VIBE3_MANAGER_MODEL", "gemini-3-flash-preview")

    captured_options = {}

    def fake_resolve_manager_agent_options(config, runtime_config, worktree=False):
        # This should NOT be called when env vars are set
        captured_options["called"] = True
        return MagicMock(backend="wrong-backend", model="wrong-model")

    with (
        patch(
            "vibe3.orchestra.agent_resolver.resolve_manager_agent_options",
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
                worktree=False,
            )
        except Exception:
            pass

    # resolve_manager_agent_options should NOT have been called
    assert not captured_options.get(
        "called"
    ), "resolve_manager_agent_options was called even though env vars were set"


@patch("vibe3.manager.worktree_manager.WorktreeManager")
def test_resolve_manager_execution_cwd_marks_worktree_when_resolved(
    mock_manager, tmp_path
):
    """When WorktreeManager returns a dedicated cwd, worktree flag should be True."""
    mock_manager.return_value.resolve_manager_cwd.return_value = (tmp_path, True)

    from vibe3.manager.manager_run_service import resolve_manager_execution_cwd

    cwd, worktree = resolve_manager_execution_cwd(
        orchestra_config=MagicMock(),
        issue_number=42,
        target_branch="task/issue-42",
        current_branch="main",
        use_worktree=True,
        session_id=None,
    )

    assert cwd == tmp_path
    assert worktree is True
    mock_manager.return_value.resolve_manager_cwd.assert_called_once_with(
        42, "task/issue-42"
    )


@patch("vibe3.manager.manager_run_service.resolve_manager_launch_cwd")
@patch("vibe3.manager.worktree_manager.WorktreeManager")
def test_resolve_manager_execution_cwd_falls_back_without_worktree(
    mock_manager, mock_launch
):
    """If WorktreeManager cannot resolve, fall back without worktree flag."""
    mock_manager.return_value.resolve_manager_cwd.return_value = (None, False)
    mock_launch.return_value = MagicMock()

    from vibe3.manager.manager_run_service import resolve_manager_execution_cwd

    cwd, worktree = resolve_manager_execution_cwd(
        orchestra_config=MagicMock(),
        issue_number=99,
        target_branch="feature/99",
        current_branch="main",
        use_worktree=True,
        session_id=None,
    )

    assert cwd == mock_launch.return_value
    assert worktree is False
    mock_launch.assert_called_once()
