"""Coverage models for layer-based coverage checking."""

from __future__ import annotations

from pydantic import BaseModel


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
    total_covered: int
    total_lines: int
    overall_percent: float

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
