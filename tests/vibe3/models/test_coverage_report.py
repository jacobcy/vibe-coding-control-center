"""Tests for CoverageReport model."""

import pytest

from vibe3.models.coverage import CoverageReport, LayerCoverage


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