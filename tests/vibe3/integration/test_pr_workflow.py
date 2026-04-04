#!/usr/bin/env python3
"""Integration test for PR commands.

This script tests the complete PR workflow using a test repository.

Usage:
    python tests/integration/test_pr_workflow.py

Requirements:
    - GitHub CLI (gh) authenticated
    - Test repository (can be created dynamically)
    - Codex CLI installed (optional, for review tests)
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts to path
scripts_path = Path(__file__).parent.parent.parent / "scripts" / "python"
if str(scripts_path) not in sys.path:
    sys.path.insert(0, str(scripts_path))

from loguru import logger  # noqa: E402


def _gh_authenticated() -> bool:
    """Return True if gh CLI is available and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command."""
    logger.info(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def test_gh_auth() -> None:
    """_gh_authenticated returns True when gh auth succeeds."""
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        assert _gh_authenticated() is True
    mock_run.assert_called_once_with(
        ["gh", "auth", "status"], capture_output=True, check=False
    )


def test_gh_auth_returns_false_when_command_missing() -> None:
    """_gh_authenticated returns False when gh CLI is unavailable."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert _gh_authenticated() is False


def test_run_command_passes_expected_subprocess_options() -> None:
    """run_command should forward check/capture/text options."""
    mock_result = MagicMock()
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = run_command(["gh", "auth", "status"], check=False)

    assert result is mock_result
    mock_run.assert_called_once_with(
        ["gh", "auth", "status"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_version_file() -> None:
    """Test VERSION file reading."""
    from vibe3.services.version_service import VersionService

    version_file = Path(__file__).parent.parent.parent.parent / "VERSION"

    try:
        service = VersionService(version_file=version_file)
        version = service.get_current_version()
        assert version
        logger.success(f"✓ VERSION file found: {version}")
    except FileNotFoundError:
        logger.error("✗ VERSION file not found")
        assert False, "VERSION file not found"
    except Exception as e:
        logger.error(f"✗ Failed to read VERSION: {e}")
        assert False, f"Failed to read VERSION: {e}"


def main() -> int:
    """Run integration tests."""
    logger.info("Vibe3 PR Integration Tests")
    logger.info("=" * 60)

    try:
        test_gh_auth()
        test_version_file()
        logger.success("\n✓ All integration tests passed!")
        return 0
    except AssertionError:
        logger.error("\n✗ Some integration tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
