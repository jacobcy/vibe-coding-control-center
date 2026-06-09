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
    from vibe3.utils.git_helpers import find_repo_root

    find_repo_root.cache_clear()
    yield
    # Clear again after test to clean up for subsequent tests
    find_repo_root.cache_clear()


@pytest.fixture(autouse=True)
def clear_prompt_manifest_cache():
    """Clear PromptManifest.load_default cache before each test to ensure isolation.

    The load_default() function uses @functools.lru_cache(maxsize=1) for
    performance, but this can leak across tests when DEFAULT_PROMPT_RECIPES_PATH
    is monkeypatched. This autouse fixture ensures each test starts with a clean cache.
    """
    from vibe3.prompts.manifest import PromptManifest

    PromptManifest.load_default.cache_clear()
    yield
    # Clear again after test to clean up for subsequent tests
    PromptManifest.load_default.cache_clear()


@pytest.fixture(autouse=True)
def isolate_database(request):
    """Use temporary database for tests to prevent production DB contamination.

    Monkeypatches GitClient.get_git_common_dir() to return a temporary directory,
    causing SQLiteClient to derive db_path as {tempdir}/vibe3/handoff.db instead
    of the real production database.

    This prevents test mock leaks and test errors from being recorded to the
    production error_log table, which could trigger FailedGate and block serve.

    Fixture scope: function (each test gets isolated temp database)
    Autouse: Yes (applies to all vibe3 tests automatically)

    Exception: Tests of GitClient itself are skipped to avoid interfering with
    unit tests that verify get_git_common_dir() behavior.

    See: https://github.com/jacobcy/vibe-coding-control-center/issues/1857
    Issue #1857 - Mock leaks contaminating production database.
    """
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.sqlite_base import _close_global_connection
    from vibe3.services.error_tracking_service import ErrorTrackingService

    # Skip patching for tests that verify GitClient.get_git_common_dir() itself
    # to avoid interfering with their assertions
    test_file = request.module.__file__
    if "test_git_client.py" in test_file:
        # Don't patch for GitClient's own unit tests
        yield
        return

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


@pytest.fixture(autouse=True)
def _silence_orchestra_log(request):
    """Prevent tests from writing to the production orchestra event log.

    append_orchestra_event() is imported by 15+ modules. Tests that exercise
    code paths calling it (heartbeat.register, dispatch coordinator, qualify
    gate, etc.) leak _MockService entries into temp/logs/orchestra/events.log
    when VIBE3_ORCHESTRA_EVENT_LOG=1 is set in the environment.

    Patches both the source module and the heartbeat import site. Individual
    tests can still monkeypatch the heartbeat local reference to capture
    events for assertions (function-scoped overrides session-scoped).

    Skipped for test_orchestra_log.py which directly tests the logging module.

    See: https://github.com/jacobcy/vibe-coding-control-center/pull/2588
    """
    from vibe3.observability.orchestra_log import _close_events_log

    _close_events_log()

    # Skip patching for tests that verify the logging module itself
    test_file = request.module.__file__
    if "test_orchestra_log.py" in test_file:
        yield
        return

    def _noop(*args: object, **kwargs: object) -> Path:
        return Path()

    with (
        patch("vibe3.observability.orchestra_log.append_orchestra_event", _noop),
        patch("vibe3.runtime.heartbeat.append_orchestra_event", _noop),
    ):
        yield
