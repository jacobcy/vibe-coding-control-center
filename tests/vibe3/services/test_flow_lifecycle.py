"""Tests for Flow lifecycle methods (create_with_branch, switch)."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.models.flow import FlowState
from vibe3.services.flow_service import FlowService


class TestCreateFlowWithBranch:
    """Tests for create_flow_with_branch method."""

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
        git.branch_exists.return_value = False
        git.has_uncommitted_changes.return_value = False
        return git

    def test_create_flow_with_branch_success(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test successful flow creation with branch."""
        service = FlowService(store=mock_store, git_client=mock_git)

        result = service.create_flow_with_branch(slug="test-feature")

        assert isinstance(result, FlowState)
        assert result.flow_slug == "test-feature"
        assert result.branch == "task/test-feature"

        mock_git.create_branch.assert_called_once_with(
            "task/test-feature", "origin/main"
        )

    def test_create_flow_with_branch_already_exists(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test creating flow when branch already exists."""
        mock_git.branch_exists.return_value = True

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(UserError, match="already exists"):
            service.create_flow_with_branch(slug="test-feature")

    def test_create_flow_with_branch_dirty_worktree(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test creating flow with uncommitted changes."""
        mock_git.has_uncommitted_changes.return_value = True

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(UserError, match="uncommitted changes"):
            service.create_flow_with_branch(slug="test-feature")

    def test_create_flow_with_branch_save_unstash(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test creating flow with --save-unstash stashes and restores."""
        mock_git.has_uncommitted_changes.return_value = True
        mock_git.stash_push.return_value = "stash@{0}"

        service = FlowService(store=mock_store, git_client=mock_git)

        result = service.create_flow_with_branch(slug="test-feature", save_unstash=True)

        assert isinstance(result, FlowState)
        mock_git.stash_push.assert_called_once()
        mock_git.stash_apply.assert_called_once_with("stash@{0}")

    def test_create_flow_with_branch_custom_start_ref(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test creating flow with custom start reference."""
        service = FlowService(store=mock_store, git_client=mock_git)

        result = service.create_flow_with_branch(
            slug="test-feature", start_ref="origin/develop"
        )

        assert isinstance(result, FlowState)
        mock_git.create_branch.assert_called_once_with(
            "task/test-feature", "origin/develop"
        )


class TestSwitchFlow:
    """Tests for switch_flow method."""

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
        git.has_uncommitted_changes.return_value = False
        return git

    def test_switch_flow_success(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test successful flow switch."""
        service = FlowService(store=mock_store, git_client=mock_git)

        result = service.switch_flow(target="task/test-feature")

        assert isinstance(result, FlowState)
        assert result.branch == "task/test-feature"
        mock_git.switch_branch.assert_called_once_with("task/test-feature")

    def test_switch_flow_with_slug_only(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test switching flow with slug only (auto-prefix)."""
        service = FlowService(store=mock_store, git_client=mock_git)

        result = service.switch_flow(target="test-feature")

        assert isinstance(result, FlowState)
        mock_git.switch_branch.assert_called_once_with("task/test-feature")

    def test_switch_flow_branch_not_found(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test switching to non-existent branch."""
        mock_git.branch_exists.return_value = False

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(UserError, match="does not exist"):
            service.switch_flow(target="task/test-feature")

    def test_switch_flow_not_in_database(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test switching to branch without flow in database."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(UserError, match="not found in database"):
            service.switch_flow(target="task/test-feature")

    def test_switch_flow_with_uncommitted_changes(
        self, mock_store: MagicMock, mock_git: MagicMock
    ) -> None:
        """Test switching flow with uncommitted changes."""
        mock_git.has_uncommitted_changes.return_value = True
        mock_git.stash_push.return_value = "stash@{0}"

        service = FlowService(store=mock_store, git_client=mock_git)

        result = service.switch_flow(target="task/test-feature")

        assert isinstance(result, FlowState)
        mock_git.stash_push.assert_called_once()
        mock_git.stash_apply.assert_called_once_with("stash@{0}")
