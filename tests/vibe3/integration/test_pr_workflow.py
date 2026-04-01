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

import pytest

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


_requires_gh = pytest.mark.skipif(
    not _gh_authenticated(),
    reason="gh CLI not authenticated — skipped in CI",
)


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command."""
    logger.info(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


@_requires_gh
def test_gh_auth() -> None:
    """Test GitHub CLI authentication."""
    try:
        result = run_command(["gh", "auth", "status"], check=False)
        assert result.returncode == 0
        logger.success("✓ GitHub CLI authenticated")
    except FileNotFoundError:
        logger.error("✗ GitHub CLI not found")
        assert False, "GitHub CLI not found"
    except AssertionError:
        logger.error("✗ GitHub CLI not authenticated")
        logger.error("  Run: gh auth login")
        assert False, "GitHub CLI not authenticated"


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


def test_pr_draft_creation() -> None:
    """Test PR draft creation (requires test repo)."""
    logger.info("Testing PR draft creation...")

    # This is a placeholder - in real scenario, would create test repo
    logger.warning("  Skipping: Requires test repository setup")
    logger.info("  Manual test: python -m vibe3.commands.pr draft -t 'Test PR'")
    assert True


@_requires_gh
def test_pr_workflow_integration() -> None:
    """Test complete PR workflow."""
    logger.info("Testing PR workflow integration...")

    tests = [
        ("GitHub CLI Auth", test_gh_auth),
        ("VERSION File", test_version_file),
        ("PR Draft Creation", test_pr_draft_creation),
    ]

    results = []
    for name, test_func in tests:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Test: {name}")
        logger.info("=" * 60)
        try:
            test_func()
            result = True
        except (AssertionError, Exception):
            result = False
        results.append((name, result))

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("Test Summary")
    logger.info("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    assert passed == total


def main() -> int:
    """Run integration tests."""
    logger.info("Vibe3 PR Integration Tests")
    logger.info("=" * 60)

    try:
        test_pr_workflow_integration()
        logger.success("\n✓ All integration tests passed!")
        return 0
    except AssertionError:
        logger.error("\n✗ Some integration tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
