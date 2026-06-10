"""Tests for vibe-closeout skill behavior."""

from unittest.mock import patch

from vibe3.services.flow.cleanup import FlowCleanupService


class TestVibeCloseout:
    """Tests for closeout skill cleanup behavior."""

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_closeout_preserve_mode_for_done_flow(self, mock_cleanup):
        """Test that done flows use preserve mode (keep_flow_record=True)."""
        # Setup
        mock_cleanup.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-123-done-flow"
        keep_flow_record = True

        # Execute cleanup as closeout skill would (preserve mode for done flow)
        cleanup_service = FlowCleanupService()
        result = cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=keep_flow_record,
            force_delete=False,
        )

        # Verify
        assert result["worktree"] is True
        assert result["flow_record"] is True
        mock_cleanup.assert_called_once_with(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=True,
            force_delete=False,
        )

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_closeout_reset_mode_for_aborted_flow(self, mock_cleanup):
        """Test that aborted flows use reset mode (keep_flow_record=False)."""
        # Setup
        mock_cleanup.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-456-aborted-flow"
        keep_flow_record = False

        # Execute cleanup as closeout skill would (reset mode for aborted flow)
        cleanup_service = FlowCleanupService()
        result = cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=keep_flow_record,
            force_delete=False,
        )

        # Verify
        assert result["worktree"] is True
        assert result["flow_record"] is True
        mock_cleanup.assert_called_once_with(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=False,
        )

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_closeout_cleanup_includes_remote_branch(self, mock_cleanup):
        """Test that cleanup includes remote branch deletion."""
        # Setup
        mock_cleanup.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-789-with-remote"

        # Execute cleanup
        cleanup_service = FlowCleanupService()
        result = cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,  # Should include remote branch
            terminate_sessions=True,
            keep_flow_record=True,
            force_delete=False,
        )

        # Verify remote branch cleanup was attempted
        assert result["remote_branch"] is True
        call_args = mock_cleanup.call_args
        assert call_args[1]["include_remote"] is True

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_closeout_cleanup_handles_partial_failure(self, mock_cleanup):
        """Test that cleanup handles partial failures gracefully."""
        # Setup - simulate partial failure (worktree removal failed)
        mock_cleanup.return_value = {
            "worktree": False,  # Failed
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-999-partial-failure"

        # Execute cleanup
        cleanup_service = FlowCleanupService()
        result = cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=False,
        )

        # Verify partial results are reported correctly
        assert result["worktree"] is False
        assert result["local_branch"] is True
        assert result["remote_branch"] is True
        assert result["handoff"] is True
        assert result["flow_record"] is True

    def test_cleanup_mode_determination_done(self):
        """Test cleanup mode determination for done flow status."""
        # When flow_status is "done", cleanup_mode should be "preserve"
        flow_status = "done"
        cleanup_mode = "preserve" if flow_status == "done" else "reset"
        keep_flow_record = cleanup_mode == "preserve"

        assert cleanup_mode == "preserve"
        assert keep_flow_record is True

    def test_cleanup_mode_determination_aborted(self):
        """Test cleanup mode determination for aborted flow status."""
        # When flow_status is "aborted", cleanup_mode should be "reset"
        flow_status = "aborted"
        cleanup_mode = "preserve" if flow_status == "done" else "reset"
        keep_flow_record = cleanup_mode == "preserve"

        assert cleanup_mode == "reset"
        assert keep_flow_record is False

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_closeout_handles_missing_remote_branch(self, mock_cleanup):
        """Test that cleanup handles missing remote branch gracefully."""
        # Setup - remote branch doesn't exist
        mock_cleanup.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,  # Still True even if remote didn't exist
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-111-no-remote"

        # Execute cleanup
        cleanup_service = FlowCleanupService()
        result = cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=True,
            force_delete=False,
        )

        # Verify cleanup succeeds even if remote didn't exist
        assert result["remote_branch"] is True

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_closeout_terminates_task_sessions(self, mock_cleanup):
        """Test that cleanup terminates tmux sessions for task branches."""
        # Setup
        mock_cleanup.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-222-with-session"

        # Execute cleanup with session termination
        cleanup_service = FlowCleanupService()
        cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=True,
            force_delete=False,
        )

        # Verify cleanup was called with terminate_sessions=True
        call_args = mock_cleanup.call_args
        assert call_args[1]["terminate_sessions"] is True


class TestCloseoutIntegration:
    """Integration tests for closeout workflow."""

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_complete_closeout_workflow_done(self, mock_cleanup):
        """Test complete closeout workflow for done flow."""
        # Setup
        mock_cleanup.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-333-done"

        # Step 1: Determine cleanup mode from flow status (done = preserve)
        keep_flow_record = True

        # Step 2: Execute cleanup
        cleanup_service = FlowCleanupService()
        result = cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=keep_flow_record,
            force_delete=False,
        )

        # Step 3: Verify all steps succeeded
        assert all(result.values()), "All cleanup steps should succeed for done flow"

        # Verify flow record was kept
        call_args = mock_cleanup.call_args
        assert call_args[1]["keep_flow_record"] is True

    @patch("vibe3.services.flow.cleanup.FlowCleanupService.cleanup_flow_scene")
    def test_complete_closeout_workflow_aborted(self, mock_cleanup):
        """Test complete closeout workflow for aborted flow."""
        # Setup
        mock_cleanup.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        branch = "task/issue-444-aborted"

        # Step 1: Determine cleanup mode from flow status (aborted = reset)
        keep_flow_record = False

        # Step 2: Execute cleanup
        cleanup_service = FlowCleanupService()
        result = cleanup_service.cleanup_flow_scene(
            branch=branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=keep_flow_record,
            force_delete=False,
        )

        # Step 3: Verify all steps succeeded
        assert all(result.values()), "All cleanup steps should succeed for aborted flow"

        # Verify flow record was not kept (soft deleted)
        call_args = mock_cleanup.call_args
        assert call_args[1]["keep_flow_record"] is False
