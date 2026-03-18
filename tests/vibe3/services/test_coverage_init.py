"""Tests for CoverageService initialization and configuration."""
from pathlib import Path

from vibe3.services.coverage_service import CoverageService


def test_coverage_service_initialization(coverage_service: CoverageService) -> None:
    """Test coverage service initialization."""
    assert coverage_service.thresholds == {
        "services": 80,
        "clients": 80,
        "commands": 80,
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