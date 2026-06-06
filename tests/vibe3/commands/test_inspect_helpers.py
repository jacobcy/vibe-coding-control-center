"""Unit tests for inspect helper functions.

Merged from:
- test_inspect_commit.py (4 tests)
- test_inspect_commits.py (9 tests)
- test_inspect_filter_score.py (9 tests)

Tests focus on internal helper functions with mocked dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.git_status_ops import _get_commit_files
from vibe3.commands.inspect_helpers import (
    calculate_pr_risk_score,
    filter_critical_files,
    get_pr_commit_count,
    get_recent_commits,
)
from vibe3.exceptions import GitError

# ========== _get_commit_files Tests (from test_inspect_commit.py) ==========


def test__get_commit_files_merge_commit_with_duplicates():
    def mock_run(cmd):
        return """file1.py
file2.py
file1.py
file3.py
file2.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
    assert len(result) == 3


def test__get_commit_files_regular_commit_no_duplicates():
    def mock_run(cmd):
        return """file1.py
file2.py
file3.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
    assert len(result) == 3


def test__get_commit_files_empty_output():
    def mock_run(cmd):
        return ""

    result = _get_commit_files(mock_run, "abc123")
    assert result == []


def test__get_commit_files_whitespace_only_lines():
    def mock_run(cmd):
        return """file1.py

file2.py

file3.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]


# ========== _get_recent_commits Tests (from test_inspect_commits.py) ==========


def test_get_recent_commits_success():
    """Successfully get recent commits."""
    with (
        patch("vibe3.services.pr.analysis.subprocess.run") as mock_run,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        # Mock subprocess.run to return commit SHAs
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\ndef456\nghi789\n",
        )

        # Mock get_commit_message
        mock_get_commit_message.side_effect = [
            "Add feature X",
            "Fix bug Y",
            "update docs",
        ]

        result = get_recent_commits(42, limit=3)

        assert len(result) == 3
        assert result[0]["sha"] == "abc123"
        assert result[0]["message"] == "Add feature X"
        assert result[1]["sha"] == "def456"
        assert result[2]["sha"] == "ghi789"


def test_get_recent_commits_limit():
    """Respect limit parameter."""
    with (
        patch("vibe3.services.pr.analysis.subprocess.run") as mock_run,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="a\nb\nc\nd\ne\nf\n",
        )
        mock_get_commit_message.return_value = "message"
        result = get_recent_commits(42, limit=3)
        assert len(result) == 3


def test_get_recent_commits_empty():
    """Handle empty commits list."""
    with patch("vibe3.services.pr.analysis.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="\n",
        )
        result = get_recent_commits(42)
        assert result == []


def test_get_recent_commits_github_error():
    """Handle GitHub API error gracefully."""
    with patch("vibe3.services.pr.analysis.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("API error")
        result = get_recent_commits(42)
        assert result == []


def test_get_recent_commits_git_error():
    """Skip commits with git errors, continue with others."""
    with (
        patch("vibe3.services.pr.analysis.subprocess.run") as mock_run,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\ndef456\nghi789\n",
        )
        # Second commit fails
        mock_get_commit_message.side_effect = [
            "Add feature X",
            GitError(operation="log", details="Not found"),
            "Update docs",
        ]
        result = get_recent_commits(42)
        # Should skip failed commit
        assert len(result) == 2
        assert result[0]["sha"] == "abc123"
        assert result[1]["sha"] == "ghi789"


def test_get_recent_commits_short_sha():
    """SHA is shortened to 7 characters."""
    with (
        patch("vibe3.services.pr.analysis.subprocess.run") as mock_run,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abcdefghijklmnopqrstuvwxyz123456\n",
        )
        mock_get_commit_message.return_value = "message"
        result = get_recent_commits(42)
        assert result[0]["sha"] == "abcdefg"  # First 7 chars


# ========== _get_pr_commit_count Tests (from test_inspect_commits.py) ==========


def test_get_pr_commit_count_success():
    """Get commit count successfully."""
    with patch("vibe3.services.pr.analysis.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="a\nb\nc\nd\ne\n",
        )
        result = get_pr_commit_count(42)
        assert result == 5


def test_get_pr_commit_count_empty():
    """Handle empty commits."""
    with patch("vibe3.services.pr.analysis.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="\n",
        )
        result = get_pr_commit_count(42)
        assert result == 0


def test_get_pr_commit_count_error():
    """Return 0 on error."""
    with patch("vibe3.services.pr.analysis.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("API error")
        result = get_pr_commit_count(42)
        assert result == 0


# ========== Fixtures for filter/score tests ==========


@pytest.fixture
def mock_config():
    """Mock get_config to return test configuration."""
    with patch("vibe3.services.pr.analysis.get_config") as mock:
        config = MagicMock()
        config.review_scope.critical_paths = ["src/vibe3/config/", "src/vibe3/clients/"]
        config.review_scope.public_api_paths = ["src/vibe3/api/"]
        mock.return_value = config
        yield mock


@pytest.fixture
def mock_generate_score():
    """Mock generate_score_report."""
    with patch("vibe3.services.pr.analysis.generate_score_report") as mock:
        mock.return_value = {
            "score": 6,
            "level": "MEDIUM",
            "block": False,
        }
        yield mock


# ========== _filter_critical_files Tests (from test_inspect_filter_score.py) ==========


def test_filter_critical_files_no_matches(mock_config):
    """No critical files when all files are non-critical."""
    files = [
        "tests/test_foo.py",
        "docs/README.md",
        "scripts/setup.sh",
    ]

    result = filter_critical_files(files)

    assert result == []


def test_filter_critical_files_all_critical(mock_config):
    """All files are critical paths."""
    files = [
        "src/vibe3/config/settings.py",
        "src/vibe3/clients/git_client.py",
    ]

    result = filter_critical_files(files)

    assert len(result) == 2
    assert result[0]["path"] == "src/vibe3/config/settings.py"
    assert result[0]["critical_path"] is True
    assert result[0]["public_api"] is False
    assert result[1]["path"] == "src/vibe3/clients/git_client.py"
    assert result[1]["critical_path"] is True


def test_filter_critical_files_public_api(mock_config):
    """Files can be public API paths."""
    files = [
        "src/vibe3/api/routes.py",
        "src/vibe3/api/handlers.py",
    ]

    result = filter_critical_files(files)

    assert len(result) == 2
    assert result[0]["public_api"] is True
    assert result[0]["critical_path"] is False


def test_filter_critical_files_mixed(mock_config):
    """Mix of critical, public API, and non-critical files."""
    files = [
        "src/vibe3/config/settings.py",  # critical
        "src/vibe3/api/routes.py",  # public API
        "tests/test_foo.py",  # non-critical
    ]

    result = filter_critical_files(files)

    assert len(result) == 2
    assert result[0]["critical_path"] is True
    assert result[1]["public_api"] is True


def test_filter_critical_files_both_tags(mock_config):
    """File can be both critical and public API."""
    files = [
        "src/vibe3/config/api.py",  # Matches both patterns
    ]

    # Update mock to match both patterns
    mock_config.return_value.review_scope.critical_paths = ["src/vibe3/config/"]
    mock_config.return_value.review_scope.public_api_paths = ["api.py"]

    result = filter_critical_files(files)

    assert len(result) == 1
    assert result[0]["critical_path"] is True
    assert result[0]["public_api"] is True


# ========== _calculate_risk_score Tests (from test_inspect_filter_score.py) ==========


def test_calculate_risk_score_no_critical(mock_generate_score):
    """Low risk when no critical files."""
    all_files = ["tests/test_foo.py", "docs/README.md"]
    critical_files = []
    impacted_modules = ["vibe3.utils"]

    result = calculate_pr_risk_score(all_files, critical_files, impacted_modules)

    assert result["score"] == 6
    assert result["level"] == "MEDIUM"

    # Verify dimensions passed to scoring
    call_args = mock_generate_score.call_args[0][0]
    assert call_args.changed_files == 2
    assert call_args.impacted_modules == 1
    assert call_args.critical_path_touch is False
    assert call_args.public_api_touch is False


def test_calculate_risk_score_with_critical(mock_generate_score):
    """Higher risk with critical files."""
    all_files = ["src/vibe3/config/settings.py", "tests/test_foo.py"]
    critical_files = [
        {
            "path": "src/vibe3/config/settings.py",
            "critical_path": True,
            "public_api": False,
        }
    ]
    impacted_modules = ["vibe3.config", "vibe3.utils"]

    calculate_pr_risk_score(all_files, critical_files, impacted_modules)

    call_args = mock_generate_score.call_args[0][0]
    assert call_args.critical_path_touch is True
    assert call_args.public_api_touch is False


def test_calculate_risk_score_with_public_api(mock_generate_score):
    """Higher risk with public API changes."""
    all_files = ["src/vibe3/api/routes.py"]
    critical_files = [
        {
            "path": "src/vibe3/api/routes.py",
            "critical_path": False,
            "public_api": True,
        }
    ]
    impacted_modules = ["vibe3.api"]

    calculate_pr_risk_score(all_files, critical_files, impacted_modules)

    call_args = mock_generate_score.call_args[0][0]
    assert call_args.critical_path_touch is False
    assert call_args.public_api_touch is True


def test_calculate_risk_score_both_tags(mock_generate_score):
    """Highest risk with both critical and public API."""
    all_files = ["src/vibe3/config/api.py"]
    critical_files = [
        {
            "path": "src/vibe3/config/api.py",
            "critical_path": True,
            "public_api": True,
        }
    ]
    impacted_modules = ["vibe3.config", "vibe3.api"]

    calculate_pr_risk_score(all_files, critical_files, impacted_modules)

    call_args = mock_generate_score.call_args[0][0]
    assert call_args.critical_path_touch is True
    assert call_args.public_api_touch is True
