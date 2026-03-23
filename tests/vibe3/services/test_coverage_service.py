"""Tests for CoverageService."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.coverage_service import CoverageService


def test_coverage_service_initialization(coverage_service: CoverageService) -> None:
    """Test coverage service initialization."""
    assert coverage_service.thresholds == {
        "services": 80,
        "clients": 70,
        "commands": 60,
    }
    assert coverage_service.project_root == Path.cwd()


def test_coverage_service_custom_thresholds() -> None:
    """Test coverage service with custom thresholds."""
    custom_thresholds = {
        "services": 90,
        "clients": 85,
        "commands": 75,
    }
    service = CoverageService(thresholds=custom_thresholds)

    assert service.thresholds == custom_thresholds


def test_custom_project_root() -> None:
    """Test coverage service with custom project root."""
    custom_root = Path("/custom/path")
    service = CoverageService(project_root=custom_root)

    assert service.project_root == custom_root


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

    def fake_subprocess_run(*args, **kwargs):
        coverage_file.write_text(json.dumps(sample_coverage_data))
        return mock_result

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        data = coverage_service._run_pytest_cov()

        assert data == sample_coverage_data
        assert "files" in data


def test_run_pytest_cov_failure(
    coverage_service: CoverageService,
    mock_project_root: Path,
) -> None:
    """Test _run_pytest_cov when pytest fails."""
    coverage_service.project_root = mock_project_root

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="error", returncode=1)

        with pytest.raises(RuntimeError, match="pytest failed"):
            coverage_service._run_pytest_cov()


def test_subprocess_command_construction(
    coverage_service: CoverageService,
    mock_project_root: Path,
    sample_coverage_data: dict,
) -> None:
    """Test that subprocess command is constructed correctly."""
    coverage_service.project_root = mock_project_root
    coverage_file = mock_project_root / "coverage.json"

    def fake_subprocess_run(*args, **kwargs):
        coverage_file.write_text(json.dumps(sample_coverage_data))
        return MagicMock(stdout="", stderr="", returncode=0)

    with patch("subprocess.run", side_effect=fake_subprocess_run) as mock_run:
        coverage_service._run_pytest_cov()

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "uv"
        assert called_cmd[1] == "run"
        assert called_cmd[2] == "pytest"
        assert "--cov=src/vibe3" in called_cmd
        # Check that coverage report path contains the expected prefix
        # (full path varies based on flow state)
        cov_report_args = [
            arg for arg in called_cmd if arg.startswith("--cov-report=json:")
        ]
        assert len(cov_report_args) == 1
        assert "coverage.json" in cov_report_args[0]
        assert "-q" in called_cmd


def test_analyze_layer(
    coverage_service: CoverageService,
    sample_coverage_data: dict,
) -> None:
    """Test _analyze_layer method."""
    services_cov = coverage_service._analyze_layer(sample_coverage_data, "services")

    assert services_cov.layer_name == "services"
    assert services_cov.covered_lines == 1000
    assert services_cov.total_lines == 1200
    assert services_cov.coverage_percent == pytest.approx(83.33, rel=0.01)
    assert services_cov.threshold == 80

    clients_cov = coverage_service._analyze_layer(sample_coverage_data, "clients")

    assert clients_cov.layer_name == "clients"
    assert clients_cov.covered_lines == 500
    assert clients_cov.total_lines == 600
    assert clients_cov.coverage_percent == pytest.approx(83.33, rel=0.01)

    commands_cov = coverage_service._analyze_layer(sample_coverage_data, "commands")

    assert commands_cov.layer_name == "commands"
    assert commands_cov.covered_lines == 1350
    assert commands_cov.total_lines == 1500
    assert commands_cov.coverage_percent == 90.0


def test_analyze_layer_missing_files(coverage_service: CoverageService) -> None:
    """Test _analyze_layer with missing layer directory."""
    data = {
        "files": {
            "src/vibe3/other/module.py": {
                "summary": {
                    "covered_lines": 100,
                    "num_statements": 200,
                }
            }
        }
    }

    layer_cov = coverage_service._analyze_layer(data, "services")

    assert layer_cov.covered_lines == 0
    assert layer_cov.total_lines == 0
    assert layer_cov.coverage_percent == 0.0
