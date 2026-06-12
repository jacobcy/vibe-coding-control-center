"""Shared fixtures for analysis service tests."""

import json
from pathlib import Path

import pytest

from vibe3.analysis.coverage_service import CoverageService


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
def snapshot_dir(tmp_path: Path) -> Path:
    """Create a temporary snapshot directory with test data."""
    snapshot_dir = tmp_path / "vibe3" / "structure" / "snapshots"
    snapshot_dir.mkdir(parents=True)

    # Create test snapshots for different branches
    snapshots = [
        {
            "snapshot_id": "2026-03-20T10-00-00_main_abc1234",
            "branch": "main",
            "commit": "abc1234",
            "commit_short": "abc1234",
            "created_at": "2026-03-20T10:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        },
        {
            "snapshot_id": "2026-03-22T15-00-00_main_def5678",
            "branch": "main",
            "commit": "def5678",
            "commit_short": "def5678",
            "created_at": "2026-03-22T15:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        },
        {
            "snapshot_id": "2026-03-23T12-00-00_feature-xyz_ghi9012",
            "branch": "feature-xyz",
            "commit": "ghi9012",
            "commit_short": "ghi9012",
            "created_at": "2026-03-23T12:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        },
    ]

    for snapshot in snapshots:
        filepath = snapshot_dir / f"{snapshot['snapshot_id']}.json"
        filepath.write_text(json.dumps(snapshot, indent=2))

    return snapshot_dir
