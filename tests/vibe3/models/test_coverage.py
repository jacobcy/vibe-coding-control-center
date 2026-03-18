"""Tests for coverage models."""

import pytest

from vibe3.models.coverage import CoverageReport, LayerCoverage


def test_layer_coverage_creation() -> None:
    """Test creating a layer coverage instance."""
    layer = LayerCoverage(
        layer_name="services",
        covered_lines=850,
        total_lines=1000,
        coverage_percent=85.0,
        threshold=80,
    )

    assert layer.layer_name == "services"
    assert layer.covered_lines == 850
    assert layer.total_lines == 1000
    assert layer.coverage_percent == 85.0
    assert layer.threshold == 80


def test_layer_coverage_is_passing() -> None:
    """Test is_passing property."""
    # Passing case: coverage >= threshold
    passing_layer = LayerCoverage(
        layer_name="services",
        covered_lines=850,
        total_lines=1000,
        coverage_percent=85.0,
        threshold=80,
    )
    assert passing_layer.is_passing is True

    # Failing case: coverage < threshold
    failing_layer = LayerCoverage(
        layer_name="clients",
        covered_lines=700,
        total_lines=1000,
        coverage_percent=70.0,
        threshold=80,
    )
    assert failing_layer.is_passing is False

    # Edge case: coverage == threshold
    edge_case = LayerCoverage(
        layer_name="commands",
        covered_lines=800,
        total_lines=1000,
        coverage_percent=80.0,
        threshold=80,
    )
    assert edge_case.is_passing is True


def test_layer_coverage_gap() -> None:
    """Test gap property."""
    # Coverage below threshold: gap should be positive
    layer_below = LayerCoverage(
        layer_name="services",
        covered_lines=700,
        total_lines=1000,
        coverage_percent=70.0,
        threshold=80,
    )
    assert layer_below.gap == 10.0

    # Coverage at threshold: gap should be 0
    layer_at = LayerCoverage(
        layer_name="clients",
        covered_lines=800,
        total_lines=1000,
        coverage_percent=80.0,
        threshold=80,
    )
    assert layer_at.gap == 0.0

    # Coverage above threshold: gap should be 0
    layer_above = LayerCoverage(
        layer_name="commands",
        covered_lines=900,
        total_lines=1000,
        coverage_percent=90.0,
        threshold=80,
    )
    assert layer_above.gap == 0.0


def test_coverage_report_creation() -> None:
    """Test creating a coverage report."""
    services = LayerCoverage(
        layer_name="services",
        covered_lines=850,
        total_lines=1000,
        coverage_percent=85.0,
        threshold=80,
    )

    clients = LayerCoverage(
        layer_name="clients",
        covered_lines=420,
        total_lines=500,
        coverage_percent=84.0,
        threshold=80,
    )

    commands = LayerCoverage(
        layer_name="commands",
        covered_lines=900,
        total_lines=1000,
        coverage_percent=90.0,
        threshold=80,
    )

    report = CoverageReport(
        services=services,
        clients=clients,
        commands=commands,
        total_covered=2170,
        total_lines=2500,
        overall_percent=86.8,
    )

    assert report.services == services
    assert report.clients == clients
    assert report.commands == commands
    assert report.total_covered == 2170
    assert report.total_lines == 2500
    assert report.overall_percent == 86.8


def test_coverage_report_all_passing() -> None:
    """Test all_passing property."""
    # All passing
    all_pass = CoverageReport(
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
    assert all_pass.all_passing is True

    # One failing
    one_fail = CoverageReport(
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
    assert one_fail.all_passing is False

    # All failing
    all_fail = CoverageReport(
        services=LayerCoverage(
            layer_name="services",
            covered_lines=600,
            total_lines=1000,
            coverage_percent=60.0,
            threshold=80,
        ),
        clients=LayerCoverage(
            layer_name="clients",
            covered_lines=350,
            total_lines=500,
            coverage_percent=70.0,
            threshold=80,
        ),
        commands=LayerCoverage(
            layer_name="commands",
            covered_lines=700,
            total_lines=1000,
            coverage_percent=70.0,
            threshold=80,
        ),
        total_covered=1650,
        total_lines=2500,
        overall_percent=66.0,
    )
    assert all_fail.all_passing is False


def test_coverage_report_get_failing_layers() -> None:
    """Test get_failing_layers method."""
    services = LayerCoverage(
        layer_name="services",
        covered_lines=700,
        total_lines=1000,
        coverage_percent=70.0,
        threshold=80,
    )

    clients = LayerCoverage(
        layer_name="clients",
        covered_lines=420,
        total_lines=500,
        coverage_percent=84.0,
        threshold=80,
    )

    commands = LayerCoverage(
        layer_name="commands",
        covered_lines=750,
        total_lines=1000,
        coverage_percent=75.0,
        threshold=80,
    )

    report = CoverageReport(
        services=services,
        clients=clients,
        commands=commands,
        total_covered=1870,
        total_lines=2500,
        overall_percent=74.8,
    )

    failing = report.get_failing_layers()

    assert len(failing) == 2
    assert services in failing
    assert commands in failing
    assert clients not in failing


def test_coverage_report_no_failing_layers() -> None:
    """Test get_failing_layers when all pass."""
    report = CoverageReport(
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

    failing = report.get_failing_layers()

    assert len(failing) == 0


def test_layer_coverage_zero_coverage() -> None:
    """Test edge case: zero coverage."""
    layer = LayerCoverage(
        layer_name="commands",
        covered_lines=0,
        total_lines=100,
        coverage_percent=0.0,
        threshold=80,
    )

    assert layer.is_passing is False
    assert layer.gap == 80.0


def test_layer_coverage_perfect_coverage() -> None:
    """Test edge case: perfect coverage."""
    layer = LayerCoverage(
        layer_name="services",
        covered_lines=1000,
        total_lines=1000,
        coverage_percent=100.0,
        threshold=80,
    )

    assert layer.is_passing is True
    assert layer.gap == 0.0