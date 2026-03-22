"""GitClient branch operations tests."""

from unittest.mock import patch

import pytest

from vibe3.clients.git_client import GitClient
from vibe3.exceptions import GitError


class TestCreateBranch:
    """create_branch tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_create_branch_default_start_ref(self, client: GitClient) -> None:
        """Test creating branch with default start_ref."""
        with patch.object(client, "_run") as mock_run:
            client.create_branch("feature/new-test")

        mock_run.assert_called_once_with(
            ["checkout", "-b", "feature/new-test", "origin/main"]
        )

    def test_create_branch_custom_start_ref(self, client: GitClient) -> None:
        """Test creating branch with custom start_ref."""
        with patch.object(client, "_run") as mock_run:
            client.create_branch("feature/new-test", start_ref="develop")

        mock_run.assert_called_once_with(
            ["checkout", "-b", "feature/new-test", "develop"]
        )


class TestSwitchBranch:
    """switch_branch tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_switch_branch_success(self, client: GitClient) -> None:
        """Test switching branch successfully."""
        with patch.object(client, "_run") as mock_run:
            client.switch_branch("feature/test")

        mock_run.assert_called_once_with(["checkout", "feature/test"])


class TestDeleteBranch:
    """delete_branch tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_delete_branch_normal(self, client: GitClient) -> None:
        """Test deleting branch normally."""
        with patch.object(client, "_run") as mock_run:
            client.delete_branch("feature/test")

        mock_run.assert_called_once_with(["branch", "-d", "feature/test"])

    def test_delete_branch_force(self, client: GitClient) -> None:
        """Test force deleting branch."""
        with patch.object(client, "_run") as mock_run:
            client.delete_branch("feature/test", force=True)

        mock_run.assert_called_once_with(["branch", "-D", "feature/test"])


class TestDeleteRemoteBranch:
    """delete_remote_branch tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_delete_remote_branch_success(self, client: GitClient) -> None:
        """Test deleting remote branch successfully."""
        with patch.object(client, "_run") as mock_run:
            client.delete_remote_branch("feature/test")

        mock_run.assert_called_once_with(["push", "origin", "--delete", "feature/test"])


class TestStashPush:
    """stash_push tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_stash_push_without_message(self, client: GitClient) -> None:
        """Test stash without message."""
        with patch.object(client, "_run") as mock_run:
            mock_run.side_effect = [
                "",  # stash push
                "stash@{0}: WIP on main: abc123 commit message",  # stash list
            ]
            stash_ref = client.stash_push()

        assert stash_ref == "stash@{0}"
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["stash", "push"])

    def test_stash_push_with_message(self, client: GitClient) -> None:
        """Test stash with message."""
        with patch.object(client, "_run") as mock_run:
            mock_run.side_effect = [
                "",  # stash push
                "stash@{0}: On main: custom message",  # stash list
            ]
            stash_ref = client.stash_push(message="custom message")

        assert stash_ref == "stash@{0}"
        mock_run.assert_any_call(["stash", "push", "-m", "custom message"])


class TestStashApply:
    """stash_apply tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_stash_apply_success(self, client: GitClient) -> None:
        """Test applying and dropping stash."""
        with patch.object(client, "_run") as mock_run:
            client.stash_apply("stash@{0}")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(["stash", "apply", "stash@{0}"])
        mock_run.assert_any_call(["stash", "drop", "stash@{0}"])


class TestHasUncommittedChanges:
    """has_uncommitted_changes tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_no_changes(self, client: GitClient) -> None:
        """Test no uncommitted changes."""
        with patch.object(client, "_run", return_value=""):
            result = client.has_uncommitted_changes()

        assert result is False

    def test_has_staged_changes(self, client: GitClient) -> None:
        """Test has staged changes."""
        with patch.object(client, "_run", side_effect=GitError("diff", "has changes")):
            result = client.has_uncommitted_changes()

        assert result is True

    def test_has_unstaged_changes(self, client: GitClient) -> None:
        """Test has unstaged changes."""
        with patch.object(
            client, "_run", side_effect=["", GitError("diff", "has changes")]
        ):
            result = client.has_uncommitted_changes()

        assert result is True


class TestBranchExists:
    """branch_exists tests."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_local_branch_exists(self, client: GitClient) -> None:
        """Test local branch exists."""
        with patch.object(client, "_run", return_value="feature/test"):
            result = client.branch_exists("feature/test")

        assert result is True

    def test_remote_branch_exists(self, client: GitClient) -> None:
        """Test remote branch exists."""
        with patch.object(client, "_run", side_effect=["", "origin/feature/test"]):
            result = client.branch_exists("feature/test")

        assert result is True

    def test_branch_not_exists(self, client: GitClient) -> None:
        """Test branch does not exist."""
        with patch.object(client, "_run", return_value=""):
            result = client.branch_exists("feature/nonexistent")

        assert result is False
