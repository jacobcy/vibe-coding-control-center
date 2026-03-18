"""Shared fixtures for PR command tests."""
import pytest

from vibe3.models.coverage import CoverageReport, LayerCoverage
from vibe3.models.pr import PRResponse, PRState


@pytest.fixture
def mock_pr_response() -> PRResponse:
    """Create mock PR response."""
    return PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,
    )


@pytest.fixture
def mock_coverage_all_passing() -> CoverageReport:
    """Create mock coverage report with all layers passing."""
    return CoverageReport(
        services=LayerCoverage(
            layer_name="services",
            covered_lines=850,
            total_lines=1000,
            coverage_percent=85.0,
            threshold=80,
        ),
        clients=LayerCoverage(
            layer_name="clients",
            covered_lines=420,
            total_lines=500,
            coverage_percent=84.0,
            threshold=80,
        ),
        commands=LayerCoverage(
            layer_name="commands",
            covered_lines=900,
            total_lines=1000,
            coverage_percent=90.0,
            threshold=80,
        ),
        total_covered=2170,
        total_lines=2500,
        overall_percent=86.8,
    )


@pytest.fixture
def mock_coverage_failing() -> CoverageReport:
    """Create mock coverage report with services layer failing."""
    return CoverageReport(
        services=LayerCoverage(
            layer_name="services",
            covered_lines=700,
            total_lines=1000,
            coverage_percent=70.0,
            threshold=80,
        ),
        clients=LayerCoverage(
            layer_name="clients",
            covered_lines=420,
            total_lines=500,
            coverage_percent=84.0,
            threshold=80,
        ),
        commands=LayerCoverage(
            layer_name="commands",
            covered_lines=900,
            total_lines=1000,
            coverage_percent=90.0,
            threshold=80,
        ),
        total_covered=2020,
        total_lines=2500,
        overall_percent=80.8,
    )


@pytest.fixture
def mock_inspect_passing():
    """Mock inspect data that passes quality gate."""
    return {
        "score": {
            "score": 3.2,
            "level": "LOW",
            "block": False,
            "reason": "Low risk changes",
        }
    }