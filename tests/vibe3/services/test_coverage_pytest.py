"""Tests for CoverageService pytest execution."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.coverage_service import CoverageService


def test_run_pytest_cov_success(
    coverage_service: CoverageService,
    mock_project_root: Path,
    sample_coverage_data: dict,
) -> None:
    """Test _run_pytest_cov success."""
    coverage_service.project_root = mock_project_root
    coverage_file = mock_project_root / "coverage.json"

    mock_result = MagicMock()
    mock_result.stdout = "pytest output"
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        coverage_file.write_text(json.dumps(sample_coverage_data))

        data = coverage_service._run_pytest_cov()

        assert data == sample_coverage_data
        assert "files" in data


def test_run_pytest_cov_failure(
    coverage_service: CoverageService,
    mock_project_root: Path,
) -> None:
    """Test _run_pytest_cov when coverage.json is not generated."""
    coverage_service.project_root = mock_project_root

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="error", returncode=1)

        with pytest.raises(RuntimeError, match="coverage.json not generated"):
            coverage_service._run_pytest_cov()


def test_subprocess_command_construction(
    coverage_service: CoverageService,
    mock_project_root: Path,
    sample_coverage_data: dict,
) -> None:
    """Test that subprocess command is constructed correctly."""
    coverage_service.project_root = mock_project_root
    coverage_file = mock_project_root / "coverage.json"
    coverage_file.write_text(json.dumps(sample_coverage_data))

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        coverage_service._run_pytest_cov()

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "uv"
        assert called_cmd[1] == "run"
        assert called_cmd[2] == "pytest"
        assert "--cov=src/vibe3" in called_cmd
        assert "--cov-report=json:coverage.json" in called_cmd
        assert "-q" in called_cmd