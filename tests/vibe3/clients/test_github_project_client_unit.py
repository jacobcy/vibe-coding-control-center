"""Unit tests for GitHubProjectClient error handling."""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from vibe3.clients.github_project_client import GitHubProjectClient
from vibe3.exceptions import GitHubError


@pytest.fixture
def client() -> GitHubProjectClient:
    """Create client instance."""
    return GitHubProjectClient("testowner", 1)


def test_graphql_errors_in_response(
    client: GitHubProjectClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test GraphQL errors in response raise GitHubError."""
    mock_result = MagicMock()
    mock_result.stdout = json.dumps(
        {
            "errors": [{"message": "Field 'invalid' doesn't exist"}],
        }
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(return_value=mock_result),
    )

    with pytest.raises(GitHubError, match="GraphQL errors"):
        client.get_project_info()


def test_project_not_found(
    client: GitHubProjectClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test project not found raises GitHubError."""
    mock_result = MagicMock()
    mock_result.stdout = json.dumps(
        {
            "data": {
                "user": {
                    "projectV2": None,
                },
            },
        }
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(return_value=mock_result),
    )

    with pytest.raises(GitHubError, match="Project #1 not found"):
        client.get_project_info()


def test_called_process_error(
    client: GitHubProjectClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test subprocess CalledProcessError raises GitHubError."""
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["gh", "api", "graphql"],
        stderr="gh auth token not found",
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=error),
    )

    with pytest.raises(GitHubError, match="gh api graphql failed"):
        client.get_project_info()


def test_json_decode_error(
    client: GitHubProjectClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test JSON decode error raises GitHubError."""
    mock_result = MagicMock()
    mock_result.stdout = "not valid json"

    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(return_value=mock_result),
    )

    with pytest.raises(GitHubError, match="Failed to parse JSON response"):
        client.get_project_info()
