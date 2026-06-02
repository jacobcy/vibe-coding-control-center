"""Shared fixtures for Vibe3 tests."""

from __future__ import annotations

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
