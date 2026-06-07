"""Coverage models for layer-based coverage checking."""

from __future__ import annotations

from pydantic import BaseModel, computed_field


class LayerCoverage(BaseModel):
    """Coverage metrics for a single architectural layer."""

    layer_name: str
    covered_lines: int
    total_lines: int
    coverage_percent: float
    threshold: int

    @property
    def is_passing(self) -> bool:
        """Check if coverage meets threshold."""
        return self.coverage_percent >= self.threshold

    @property
    def gap(self) -> float:
        """Calculate coverage gap to threshold."""
        return max(0.0, self.threshold - self.coverage_percent)


class CoverageReport(BaseModel):
    """Aggregated coverage report for all layers."""

    services: LayerCoverage
    clients: LayerCoverage
    commands: LayerCoverage

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_covered(self) -> int:
        """Total covered lines across all layers."""
        return (
            self.services.covered_lines
            + self.clients.covered_lines
            + self.commands.covered_lines
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_lines(self) -> int:
        """Total lines across all layers."""
        return (
            self.services.total_lines
            + self.clients.total_lines
            + self.commands.total_lines
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_percent(self) -> float:
        """Overall coverage percentage."""
        total = self.total_lines
        return (self.total_covered / total * 100) if total > 0 else 0.0

    @property
    def all_passing(self) -> bool:
        """Check if all layers meet their thresholds."""
        return all(
            [
                self.services.is_passing,
                self.clients.is_passing,
                self.commands.is_passing,
            ]
        )

    def get_failing_layers(self) -> list[LayerCoverage]:
        """Get list of layers that failed their thresholds."""
        layers = [self.services, self.clients, self.commands]
        return [layer for layer in layers if not layer.is_passing]
