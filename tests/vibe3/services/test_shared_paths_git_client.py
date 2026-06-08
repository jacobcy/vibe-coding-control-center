"""Tests for git_path_client module.

Verifies DI injection behavior for GitClient wrapper functions.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.services.git_path_client import (
    GitPathProtocol,
    _get_git_client,
    find_worktree_path_for_branch,
    get_git_common_dir,
    get_worktree_root,
)


@pytest.fixture
def mock_git_client() -> MagicMock:
    """Create a mock GitClient."""
    mock = MagicMock(spec=GitPathProtocol)
    mock.get_git_common_dir.return_value = "/path/to/.git"
    mock.get_worktree_root.return_value = "/path/to/worktree"
    mock.get_current_branch.return_value = "main"
    mock.find_worktree_path_for_branch.return_value = Path("/path/to/worktree")
    return mock


def test_get_git_client_creates_instance_when_none() -> None:
    """Test that _get_git_client creates a new instance when no parameter is passed."""
    # When git_client is None, it should create a real GitClient instance
    client = _get_git_client(None)

    # Verify it returns something (can't easily verify it's a real GitClient
    # without importing it, but we can verify it has the protocol methods)
    assert hasattr(client, "get_git_common_dir")
    assert hasattr(client, "get_worktree_root")
    assert hasattr(client, "find_worktree_path_for_branch")


def test_get_git_client_returns_mock_when_provided(mock_git_client: MagicMock) -> None:
    """Test that _get_git_client returns the provided mock client."""
    client = _get_git_client(mock_git_client)

    # Should return the same mock
    assert client is mock_git_client


def test_get_git_common_dir_with_mock(mock_git_client: MagicMock) -> None:
    """Test that get_git_common_dir uses injected client."""
    result = get_git_common_dir(git_client=mock_git_client)

    assert result == "/path/to/.git"
    mock_git_client.get_git_common_dir.assert_called_once()


def test_get_worktree_root_with_mock(mock_git_client: MagicMock) -> None:
    """Test that get_worktree_root uses injected client."""
    result = get_worktree_root(git_client=mock_git_client)

    assert result == "/path/to/worktree"
    mock_git_client.get_worktree_root.assert_called_once()


def test_find_worktree_path_for_branch_with_mock(mock_git_client: MagicMock) -> None:
    """Test that find_worktree_path_for_branch uses injected client."""
    result = find_worktree_path_for_branch("feature-branch", git_client=mock_git_client)

    assert result == Path("/path/to/worktree")
    mock_git_client.find_worktree_path_for_branch.assert_called_once_with(
        "feature-branch"
    )


def test_get_git_common_dir_handles_exception(mock_git_client: MagicMock) -> None:
    """Test that get_git_common_dir returns empty string on exception."""
    mock_git_client.get_git_common_dir.side_effect = OSError("git error")

    result = get_git_common_dir(git_client=mock_git_client)

    assert result == ""


def test_get_worktree_root_handles_exception(mock_git_client: MagicMock) -> None:
    """Test that get_worktree_root returns empty string on exception."""
    mock_git_client.get_worktree_root.side_effect = ValueError("worktree error")

    result = get_worktree_root(git_client=mock_git_client)

    assert result == ""


def test_find_worktree_path_for_branch_handles_exception(
    mock_git_client: MagicMock,
) -> None:
    """Test that find_worktree_path_for_branch returns None on exception."""
    mock_git_client.find_worktree_path_for_branch.side_effect = OSError("not found")

    result = find_worktree_path_for_branch("missing-branch", git_client=mock_git_client)

    assert result is None


def test_di_injection_pattern_in_service_context(mock_git_client: MagicMock) -> None:
    """Test that DI pattern works in a simulated service context.

    This test demonstrates how a service would use the injected client
    across multiple operations.
    """
    # Simulate a service that uses multiple git_path_client functions
    common_dir = get_git_common_dir(git_client=mock_git_client)
    worktree_root = get_worktree_root(git_client=mock_git_client)
    branch_path = find_worktree_path_for_branch(
        "feature-branch", git_client=mock_git_client
    )

    # All operations should use the same mock client
    assert common_dir == "/path/to/.git"
    assert worktree_root == "/path/to/worktree"
    assert branch_path == Path("/path/to/worktree")

    # Verify all methods were called on the mock
    mock_git_client.get_git_common_dir.assert_called_once()
    mock_git_client.get_worktree_root.assert_called_once()
    mock_git_client.find_worktree_path_for_branch.assert_called_once_with(
        "feature-branch"
    )


def test_real_git_client_instance_creation() -> None:
    """Test that a real GitClient instance can be created when needed.

    This verifies the fallback path (no DI) still works.
    """
    # Create a real instance (no mock)
    client = _get_git_client(None)

    # Should be able to call methods (though they may fail in test environment)
    # This test mainly verifies the import and instantiation path works
    assert hasattr(client, "get_git_common_dir")
    assert hasattr(client, "get_worktree_root")
    assert hasattr(client, "find_worktree_path_for_branch")
    assert hasattr(client, "get_current_branch")
