"""Shared fixtures for services tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.analysis.coverage_service import CoverageService
from vibe3.services.task_resume_operations import TaskResumeOperations


@pytest.fixture(autouse=True)
def stable_worktree_actor(monkeypatch):
    """Avoid real git identity lookups during flow creation tests."""
    monkeypatch.setattr(
        "vibe3.services.flow_write_mixin.SignatureService.get_worktree_actor",
        lambda: "test-actor",
    )
    monkeypatch.setattr(
        "vibe3.services.flow_read_mixin.GitHubClient.get_pr",
        lambda self, pr_number=None, branch=None: None,
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


@pytest.fixture
def make_operations() -> TaskResumeOperations:
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
