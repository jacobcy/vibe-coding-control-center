"""Tests for LayerCoverage model."""

from vibe3.models.coverage import LayerCoverage


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
