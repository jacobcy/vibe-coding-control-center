"""Tests for dispatch error propagation and worktree resolution."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.environment.worktree import WorktreeManager


class TestWorktreePathRecording:
    """Test that worktree_path is recorded to flow_state on creation."""

    def test_record_worktree_path_writes_to_flow_state(self):
        """Call flow_service.update_flow_metadata with worktree_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()
            (repo_path / ".git").mkdir()

            config = MagicMock()
            config.scene_base_ref = "main"
            mock_flow_service = MagicMock()
            wm = WorktreeManager(config, repo_path, flow_service=mock_flow_service)

            wm.lifecycle.record_worktree_path("task/issue-100", "/some/path")
            mock_flow_service.update_flow_metadata.assert_called_once_with(
                "task/issue-100", worktree_path="/some/path"
            )


class TestResolveManagerCwd:
    """Tests for worktree resolution with recorded worktree_path."""

    def test_uses_recorded_worktree_path_when_valid(self):
        """When flow_state has valid worktree_path, use it directly."""
        from vibe3.models.flow import FlowState

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()
            (repo_path / ".git").mkdir()

            # Create recorded worktree
            recorded = Path(tmpdir) / "worktrees" / "task-issue-100"
            recorded.mkdir(parents=True)
            (recorded / ".git").write_text("ref: refs/heads/task/issue-100\n")

            config = MagicMock()
            config.scene_base_ref = "main"
            mock_flow_service = MagicMock()
            flow_state = FlowState(
                branch="task/issue-100",
                flow_slug="issue-100",
                worktree_path=str(recorded),
            )
            mock_flow_service.get_flow_state.return_value = flow_state
            wm = WorktreeManager(config, repo_path, flow_service=mock_flow_service)

            with (
                patch.object(
                    wm.lifecycle, "validate_branch_matches", return_value=True
                ),
                patch.object(wm, "align_auto_scene_to_base", return_value=True),
            ):
                result, is_missing = wm.resolve_manager_cwd(100, "task/issue-100")

                assert result == recorded
                assert is_missing is False

    def test_falls_back_when_recorded_path_stale(self):
        """When recorded worktree_path doesn't exist, fall back to inference."""
        from vibe3.models.flow import FlowState

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()
            (repo_path / ".git").mkdir()

            config = MagicMock()
            config.scene_base_ref = "main"
            mock_flow_service = MagicMock()
            # Recorded path doesn't exist
            flow_state = FlowState(
                branch="task/issue-100",
                flow_slug="issue-100",
                worktree_path="/nonexistent/path",
            )
            mock_flow_service.get_flow_state.return_value = flow_state
            wm = WorktreeManager(config, repo_path, flow_service=mock_flow_service)

            with (
                patch(
                    "vibe3.environment.worktree_support.is_current_branch",
                    return_value=False,
                ),
                patch(
                    "vibe3.environment.worktree_support.find_worktree_for_branch",
                    return_value=None,
                ),
            ):
                # acquire_issue_worktree will be called as fallback
                with patch.object(wm, "acquire_issue_worktree") as mock_acquire:
                    mock_ctx = MagicMock()
                    mock_ctx.path = Path(tmpdir) / "new-worktree"
                    mock_acquire.return_value = mock_ctx
                    with patch.object(
                        wm, "align_auto_scene_to_base", return_value=True
                    ):
                        result, _ = wm.resolve_manager_cwd(100, "task/issue-100")

                        mock_acquire.assert_called_once()

    def test_validate_branch_matches_exact_ref(self):
        """validate_branch_matches returns True when HEAD matches expected branch."""
        from vibe3.environment.worktree_lifecycle import WorktreeLifecycle

        wt_path = Path("/wt")
        expected_branch = "task/issue-100"

        # Mock subprocess.run to simulate git rev-parse output
        mock_result = MagicMock()
        mock_result.stdout = "task/issue-100\n"
        with patch("subprocess.run", return_value=mock_result):
            result = WorktreeLifecycle.validate_branch_matches(wt_path, expected_branch)
            assert result is True

    def test_validate_branch_matches_rejects_mismatch(self):
        """Return False when HEAD references a different branch."""
        from vibe3.environment.worktree_lifecycle import WorktreeLifecycle

        wt_path = Path("/wt")
        expected_branch = "task/issue-100"

        # Mock subprocess.run to simulate different branch
        mock_result = MagicMock()
        mock_result.stdout = "task/issue-200\n"
        with patch("subprocess.run", return_value=mock_result):
            result = WorktreeLifecycle.validate_branch_matches(wt_path, expected_branch)
            assert result is False


class TestFailedGateExecThreshold:
    """Tests for E_EXEC threshold in FailedGate."""

    def test_e_exec_threshold_triggers_failed_gate(self):
        """E_EXEC_* errors reaching threshold should trigger FailedGate."""
        from vibe3.orchestra.failed_gate import FailedGate

        # ErrorTrackingService is imported via public API inside _check_error_threshold
        with patch("vibe3.services.ErrorTrackingService") as mock_ets:
            mock_instance = MagicMock()
            mock_instance.has_critical_error.return_value = False
            mock_instance.has_model_config_error.return_value = False
            mock_instance.get_threshold_error_count.return_value = 2
            mock_ets.get_instance.return_value = mock_instance
            mock_ets.THRESHOLD_COUNT = 2
            mock_ets.TIME_WINDOW_MINUTES = 10

            with patch("sqlite3.connect"):
                gate = FailedGate()
                result = gate._check_error_threshold()

                assert result.blocked is True
                assert "ERROR-severity threshold" in (result.reason or "")

    def test_e_exec_below_threshold_passes(self):
        """Single E_EXEC_* error below threshold should not trigger."""
        from vibe3.orchestra.failed_gate import FailedGate

        with patch("vibe3.services.ErrorTrackingService") as mock_ets:
            mock_instance = MagicMock()
            mock_instance.has_critical_error.return_value = False
            mock_instance.has_model_config_error.return_value = False
            mock_instance.get_threshold_error_count.return_value = 1
            mock_ets.get_instance.return_value = mock_instance
            mock_ets.THRESHOLD_COUNT = 2

            with patch("sqlite3.connect"):
                gate = FailedGate()
                result = gate._check_error_threshold()

                assert result.blocked is False


class TestErrorCodes:
    """Tests for error code classification."""

    def test_is_exec_error(self):
        from vibe3.exceptions.error_codes import is_exec_error

        assert is_exec_error("E_EXEC_NO_OUTPUT") is True
        assert is_exec_error("E_EXEC_UNKNOWN") is True
        assert is_exec_error("E_API_TIMEOUT") is False
        assert is_exec_error("E_MODEL_CONFIG") is False
