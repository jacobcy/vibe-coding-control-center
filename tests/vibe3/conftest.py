"""Shared fixtures for Vibe3 tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class CompletedProcess:
    """Minimal mock for subprocess.CompletedProcess."""

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture(autouse=True)
def clear_find_repo_root_cache():
    """Clear find_repo_root cache before each test to ensure isolation.

    The find_repo_root() function uses @functools.lru_cache(maxsize=1) for
    performance, but this can leak across tests when mocks are used. This
    autouse fixture ensures each test starts with a clean cache.

    See: https://github.com/jacobcy/vibe-coding-control-center/pull/1840
    Copilot review comment on test isolation with lru_cache.
    """
    from vibe3.clients.git_client import find_repo_root

    find_repo_root.cache_clear()
    yield
    # Clear again after test to clean up for subsequent tests
    find_repo_root.cache_clear()


@pytest.fixture(autouse=True)
def isolate_database():
    """Use temporary database for tests to prevent production DB contamination.

    Monkeypatches GitClient.get_git_common_dir() to return a temporary directory,
    causing SQLiteClient to derive db_path as {tempdir}/vibe3/handoff.db instead
    of the real production database.

    This prevents test mock leaks and test errors from being recorded to the
    production error_log table, which could trigger FailedGate and block serve.

    Fixture scope: function (each test gets isolated temp database)
    Autouse: Yes (applies to all vibe3 tests automatically)

    See: https://github.com/jacobcy/vibe-coding-control-center/issues/1857
    Issue #1857 - Mock leaks contaminating production database.
    """
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.sqlite_base import _close_global_connection
    from vibe3.services.error_tracking_service import ErrorTrackingService

    # Create temporary directory for this test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch get_git_common_dir to return temp directory
        with patch.object(GitClient, "get_git_common_dir", return_value=tmpdir):
            # Clear process-wide state to force re-initialization with temp DB.
            # ErrorTrackingService may otherwise reuse a default singleton from a
            # previous test, including a store bound to another database path.
            _close_global_connection()
            ErrorTrackingService.clear_instance()

            yield Path(tmpdir)

            # Cleanup: close global connection and drop service singletons after test
            _close_global_connection()
            ErrorTrackingService.clear_instance()
