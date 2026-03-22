"""Tests for Flow operations (close, block, abort)."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.services.flow_service import FlowService


class TestCloseFlow:
    """Tests for close_flow method."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create a mock SQLiteClient."""
        store = MagicMock(spec=SQLiteClient)
        store.get_flow_state.return_value = {
            "branch": "task/test-feature",
            "flow_slug": "test-feature",
            "flow_status": "active",
            "task_issue_number": None,
            "pr_number": None,
            "next_step": None,
            "updated_at": "2026-03-23T00:00:00",
        }
        return store

    @pytest.fixture
    def mock_git(self) -> MagicMock:
        """Create a mock GitClient."""
        git = MagicMock(spec=GitClient)
        git.branch_exists.return_value = True
        git.get_current_branch.return_value = "main"
        return git

    def test_close_flow_success(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test successful flow closure."""
        service = FlowService(store=mock_store, git_client=mock_git)

        service.close_flow(branch="task/test-feature")

        mock_git.delete_remote_branch.assert_called_once_with("task/test-feature")
        mock_git.delete_branch.assert_called_once_with("task/test-feature", force=True)
        mock_store.update_flow_state.assert_called()

    def test_close_flow_not_found(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test closing non-existent flow."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(UserError, match="Flow not found"):
            service.close_flow(branch="task/test-feature")

    def test_close_flow_switch_from_current_branch(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test closing current branch switches to main first."""
        mock_git.get_current_branch.return_value = "task/test-feature"

        service = FlowService(store=mock_store, git_client=mock_git)

        service.close_flow(branch="task/test-feature")

        mock_git.switch_branch.assert_called_once_with("main")

    def test_close_flow_remote_branch_failure_continues(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test that remote branch deletion failure doesn't stop local deletion."""
        mock_git.delete_remote_branch.side_effect = Exception("Remote error")

        service = FlowService(store=mock_store, git_client=mock_git)

        service.close_flow(branch="task/test-feature")

        mock_git.delete_branch.assert_called_once()


class TestBlockFlow:
    """Tests for block_flow method."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create a mock SQLiteClient."""
        store = MagicMock(spec=SQLiteClient)
        store.get_flow_state.return_value = {
            "branch": "task/test-feature",
            "flow_slug": "test-feature",
            "flow_status": "active",
            "task_issue_number": None,
            "next_step": None,
            "updated_at": "2026-03-23T00:00:00",
        }
        return store

    @pytest.fixture
    def mock_git(self) -> MagicMock:
        """Create a mock GitClient."""
        return MagicMock(spec=GitClient)

    def test_block_flow_with_reason(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test blocking flow with reason."""
        service = FlowService(store=mock_store, git_client=mock_git)

        service.block_flow(branch="task/test-feature", reason="Waiting for API")

        mock_store.update_flow_state.assert_called_once_with(
            "task/test-feature",
            flow_status="blocked",
            blocked_by="Waiting for API",
        )

    def test_block_flow_with_issue(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test blocking flow with dependency issue."""
        service = FlowService(store=mock_store, git_client=mock_git)

        service.block_flow(branch="task/test-feature", blocked_by_issue=218)

        # Should call link_issue through TaskService
        mock_store.add_issue_link.assert_called_once()

    def test_block_flow_with_issue_auto_reason(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test blocking flow with issue auto-generates reason."""
        service = FlowService(store=mock_store, git_client=mock_git)

        service.block_flow(branch="task/test-feature", blocked_by_issue=218)

        mock_store.update_flow_state.assert_called_once()
        call_kwargs = mock_store.update_flow_state.call_args[1]
        assert "blocked_by" in call_kwargs
        assert "#218" in call_kwargs["blocked_by"]

    def test_block_flow_not_found(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test blocking non-existent flow."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(UserError, match="Flow not found"):
            service.block_flow(branch="task/test-feature")


class TestAbortFlow:
    """Tests for abort_flow method."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create a mock SQLiteClient."""
        store = MagicMock(spec=SQLiteClient)
        store.get_flow_state.return_value = {
            "branch": "task/test-feature",
            "flow_slug": "test-feature",
            "flow_status": "active",
            "task_issue_number": None,
            "next_step": None,
            "updated_at": "2026-03-23T00:00:00",
        }
        return store

    @pytest.fixture
    def mock_git(self) -> MagicMock:
        """Create a mock GitClient."""
        git = MagicMock(spec=GitClient)
        git.branch_exists.return_value = True
        git.get_current_branch.return_value = "main"
        return git

    def test_abort_flow_success(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test successful flow abort."""
        service = FlowService(store=mock_store, git_client=mock_git)

        service.abort_flow(branch="task/test-feature")

        mock_git.delete_remote_branch.assert_called_once_with("task/test-feature")
        mock_git.delete_branch.assert_called_once_with("task/test-feature", force=True)
        mock_store.update_flow_state.assert_called_once_with(
            "task/test-feature", flow_status="aborted"
        )

    def test_abort_flow_not_found(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test aborting non-existent flow."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(UserError, match="Flow not found"):
            service.abort_flow(branch="task/test-feature")

    def test_abort_flow_switch_from_current_branch(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test aborting current branch switches to main first."""
        mock_git.get_current_branch.return_value = "task/test-feature"

        service = FlowService(store=mock_store, git_client=mock_git)

        service.abort_flow(branch="task/test-feature")

        mock_git.switch_branch.assert_called_once_with("main")
