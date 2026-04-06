"""Tests for manager_run_coordinator."""

from unittest.mock import Mock

import pytest

from vibe3.manager.manager_run_coordinator import ManagerRunCoordinator


class TestManagerRunCoordinator:
    """Tests for ManagerRunCoordinator."""

    @pytest.fixture
    def mock_store(self):
        """Mock SQLiteClient."""
        return Mock()

    @pytest.fixture
    def coordinator(self, mock_store):
        """Create coordinator with mock store."""
        return ManagerRunCoordinator(store=mock_store)

    def test_handle_post_run_outcome_closed_issue_ready_state(
        self, coordinator, mock_store
    ):
        """Test abandon flow when issue closed from ready state."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"issue_state": "closed", "flow_status": "active"}

        result = coordinator.handle_post_run_outcome(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is True
        # Verify abandon flow was called
        assert mock_store.add_event.called

    def test_handle_post_run_outcome_closed_issue_handoff_state(
        self, coordinator, mock_store
    ):
        """Test abandon flow when issue closed from handoff state."""
        before_snapshot = {"state_label": "state/handoff"}
        after_snapshot = {"issue_state": "closed"}

        result = coordinator.handle_post_run_outcome(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is True

    def test_handle_post_run_outcome_issue_not_closed(self, coordinator):
        """Test no action when issue not closed."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"issue_state": "open"}

        result = coordinator.handle_post_run_outcome(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is False

    def test_check_progress_and_block_if_noop_blocks_when_no_progress(
        self, coordinator, mock_store
    ):
        """Test blocking when manager makes no progress."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"state_label": "state/ready"}

        result = coordinator.check_progress_and_block_if_noop(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is True
        assert mock_store.add_event.called

    def test_check_progress_and_block_if_noop_passes_when_progress(
        self, coordinator, mock_store
    ):
        """Test no blocking when manager makes progress."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"state_label": "state/handoff"}

        result = coordinator.check_progress_and_block_if_noop(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is False
