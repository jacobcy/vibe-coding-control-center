"""Tests for CoverageService layer analysis."""
import pytest

from vibe3.services.coverage_service import CoverageService


def test_analyze_layer(
    coverage_service: CoverageService,
    sample_coverage_data: dict,
) -> None:
    """Test _analyze_layer method."""
    services_cov = coverage_service._analyze_layer(
        sample_coverage_data, "services"
    )

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

    commands_cov = coverage_service._analyze_layer(
        sample_coverage_data, "commands"
    )

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