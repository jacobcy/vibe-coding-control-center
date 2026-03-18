"""Shared fixtures for coverage service tests."""
import json
from pathlib import Path

import pytest

from vibe3.services.coverage_service import CoverageService


@pytest.fixture
def coverage_service() -> CoverageService:
    """Create coverage service fixture."""
    return CoverageService()


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