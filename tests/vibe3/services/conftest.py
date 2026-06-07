"""Shared fixtures for services tests."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.analysis.coverage_service import CoverageService
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.services.task import TaskResumeOperations


@pytest.fixture(autouse=True)
def block_gh_subprocess(request, monkeypatch):
    """Block real gh CLI calls in unit tests.

    Fails the test with a clear message if subprocess.run is called with
    "gh" as the first argument. Tests that intentionally need gh should be
    marked @pytest.mark.integration.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return

    import subprocess

    _real_run = subprocess.run

    def _guarded_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "gh":
            test_id = os.environ.get("PYTEST_CURRENT_TEST", "unknown")
            raise RuntimeError(
                f"Blocked gh CLI call in unit test: {' '.join(cmd[:4])}\n"
                f"Test: {test_id}\n"
                f"If this test needs real gh, mark it with @pytest.mark.integration"
            )
        if isinstance(cmd, str) and cmd.strip().startswith("gh "):
            test_id = os.environ.get("PYTEST_CURRENT_TEST", "unknown")
            raise RuntimeError(
                f"Blocked gh CLI call in unit test (shell=True): {cmd[:60]}\n"
                f"Test: {test_id}\n"
                f"If this test needs real gh, mark it with @pytest.mark.integration"
            )
        return _real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _guarded_run)
    yield


@pytest.fixture(autouse=True)
def stable_worktree_actor(monkeypatch):
    """Avoid real git/GitHub lookups during flow creation tests."""
    monkeypatch.setattr(
        "vibe3.services.flow_write_mixin.SignatureService.get_worktree_actor",
        lambda: "test-actor",
    )

    mock_gh = MagicMock(spec=GitHubClient)
    mock_gh.get_pr.return_value = None
    mock_gh.view_issue.return_value = None
    mock_gh.list_prs_for_branch.return_value = []
    mock_gh.get_pr_diff.return_value = ""

    monkeypatch.setattr(
        "vibe3.services.flow_read_mixin.GitHubClient",
        lambda: mock_gh,
    )
    monkeypatch.setattr(
        "vibe3.services.flow_transition.GitHubClient",
        lambda: mock_gh,
    )


@pytest.fixture
def coverage_service() -> CoverageService:
    """Create coverage service fixture with explicit thresholds."""
    return CoverageService(
        thresholds={"services": 80, "clients": 70, "commands": 60},
    )


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create a mock project root with coverage.json."""
    return tmp_path


@pytest.fixture
def sample_coverage_data() -> dict:
    """Sample coverage data for testing."""
    return {
        "files": {
            "src/vibe3/services/pr_service.py": {
                "summary": {
                    "covered_lines": 850,
                    "num_statements": 1000,
                }
            },
            "src/vibe3/services/flow_service.py": {
                "summary": {
                    "covered_lines": 150,
                    "num_statements": 200,
                }
            },
            "src/vibe3/clients/github_client.py": {
                "summary": {
                    "covered_lines": 420,
                    "num_statements": 500,
                }
            },
            "src/vibe3/clients/sqlite_client.py": {
                "summary": {
                    "covered_lines": 80,
                    "num_statements": 100,
                }
            },
            "src/vibe3/commands/pr_lifecycle.py": {
                "summary": {
                    "covered_lines": 900,
                    "num_statements": 1000,
                }
            },
            "src/vibe3/commands/flow_commands.py": {
                "summary": {
                    "covered_lines": 450,
                    "num_statements": 500,
                }
            },
        }
    }


def _make_operations() -> TaskResumeOperations:
    """Create a TaskResumeOperations instance with mocked dependencies."""
    git_client = MagicMock()
    github_client = MagicMock()
    flow_service = MagicMock()
    flow_service.store = MagicMock()
    label_service = MagicMock()
    issue_flow_service = MagicMock()
    issue_flow_service.is_task_branch.return_value = True
    return TaskResumeOperations(
        git_client=git_client,
        github_client=github_client,
        flow_service=flow_service,
        label_service=label_service,
        issue_flow_service=issue_flow_service,
    )


def _mock_label_service():
    """Create a mock LabelService for BlockedStateService.unblock tests."""
    mock_label = MagicMock()
    mock_label.confirm_issue_state = MagicMock()
    mock_label.get_state = MagicMock(return_value=IssueState.READY)
    return mock_label
