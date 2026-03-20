"""Unit tests for filter and score helper functions.

Tests focus on _filter_critical_files and _calculate_risk_score with
mocked dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.commands.inspect_helpers import (
    _calculate_risk_score,
    _filter_critical_files,
)


@pytest.fixture
def mock_config():
    """Mock get_config to return test configuration."""
    with patch("vibe3.commands.inspect_pr_helpers.get_config") as mock:
        config = MagicMock()
        config.review_scope.critical_paths = ["src/vibe3/config/", "src/vibe3/clients/"]
        config.review_scope.public_api_paths = ["src/vibe3/api/"]
        mock.return_value = config
        yield mock


# ========== _filter_critical_files Tests ==========


def test_filter_critical_files_no_matches(mock_config):
    """No critical files when all files are non-critical."""
    files = [
        "tests/test_foo.py",
        "docs/README.md",
        "scripts/setup.sh",
    ]

    result = _filter_critical_files(files)

    assert result == []


def test_filter_critical_files_all_critical(mock_config):
    """All files are critical paths."""
    files = [
        "src/vibe3/config/settings.py",
        "src/vibe3/clients/git_client.py",
    ]

    result = _filter_critical_files(files)

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

    result = _filter_critical_files(files)

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

    result = _filter_critical_files(files)

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

    result = _filter_critical_files(files)

    assert len(result) == 1
    assert result[0]["critical_path"] is True
    assert result[0]["public_api"] is True


# ========== _calculate_risk_score Tests ==========


@pytest.fixture
def mock_generate_score():
    """Mock generate_score_report."""
    with patch("vibe3.commands.inspect_pr_helpers.generate_score_report") as mock:
        mock.return_value = {
            "score": 6,
            "level": "MEDIUM",
            "block": False,
        }
        yield mock


def test_calculate_risk_score_no_critical(mock_generate_score):
    """Low risk when no critical files."""
    all_files = ["tests/test_foo.py", "docs/README.md"]
    critical_files = []
    impacted_modules = ["vibe3.utils"]

    result = _calculate_risk_score(all_files, critical_files, impacted_modules)

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

    _calculate_risk_score(all_files, critical_files, impacted_modules)

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

    _calculate_risk_score(all_files, critical_files, impacted_modules)

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

    _calculate_risk_score(all_files, critical_files, impacted_modules)

    call_args = mock_generate_score.call_args[0][0]
    assert call_args.critical_path_touch is True
    assert call_args.public_api_touch is True
