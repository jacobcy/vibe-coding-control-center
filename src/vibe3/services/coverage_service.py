"""Coverage service for running pytest with coverage analysis."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.models.coverage import CoverageReport, LayerCoverage


class CoverageService:
    """Service for running and analyzing test coverage by architectural layer."""

    # Default coverage thresholds per layer
    DEFAULT_THRESHOLDS = {
        "services": 80,
        "clients": 80,
        "commands": 80,
    }

    def __init__(
        self,
        thresholds: dict[str, int] | None = None,
        project_root: Path | None = None,
    ):
        """Initialize coverage service.

        Args:
            thresholds: Custom coverage thresholds per layer
            project_root: Project root directory (defaults to cwd)
        """
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.project_root = project_root or Path.cwd()

    def run_coverage_check(self) -> CoverageReport:
        """Run pytest with coverage and generate layer-based report.

        Returns:
            CoverageReport with per-layer coverage metrics

        Raises:
            RuntimeError: If coverage run fails
        """
        logger.info("Running coverage check")

        # 1. Run pytest with coverage
        coverage_data = self._run_pytest_cov()

        # 2. Analyze by layer
        services_cov = self._analyze_layer(coverage_data, "services")
        clients_cov = self._analyze_layer(coverage_data, "clients")
        commands_cov = self._analyze_layer(coverage_data, "commands")

        # 3. Build report
        total_covered = (
            services_cov.covered_lines
            + clients_cov.covered_lines
            + commands_cov.covered_lines
        )
        total_lines = (
            services_cov.total_lines
            + clients_cov.total_lines
            + commands_cov.total_lines
        )
        overall_percent = (
            (total_covered / total_lines * 100) if total_lines > 0 else 0.0
        )

        report = CoverageReport(
            services=services_cov,
            clients=clients_cov,
            commands=commands_cov,
            total_covered=total_covered,
            total_lines=total_lines,
            overall_percent=overall_percent,
        )

        logger.info(
            f"Coverage check complete: {overall_percent:.1f}% overall, "
            f"all_passing={report.all_passing}"
        )

        return report

    def _run_pytest_cov(self) -> dict[str, Any]:
        """Run pytest with --cov --cov-json and parse output.

        Returns:
            Parsed coverage data from coverage.json

        Raises:
            RuntimeError: If pytest or coverage run fails
        """
        cov_file = self.project_root / "coverage.json"

        cmd = [
            "uv",
            "run",
            "pytest",
            "--cov=src/vibe3",
            "--cov-report=json:coverage.json",
            "--cov-report=term-missing:skip-covered",
            "-q",  # Quiet mode
        ]

        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
            )

            # Log pytest output for debugging
            if result.stdout:
                logger.debug(f"pytest stdout:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"pytest stderr:\n{result.stderr}")

            # Parse coverage.json
            if not cov_file.exists():
                raise RuntimeError("coverage.json not generated")

            with open(cov_file) as f:
                data: dict[str, Any] = json.load(f)

            return data

        except Exception as e:
            logger.error(f"Failed to run coverage: {e}")
            raise RuntimeError(f"Coverage run failed: {e}") from e

    def _analyze_layer(
        self, coverage_data: dict[str, Any], layer_name: str
    ) -> LayerCoverage:
        """Analyze coverage for a specific architectural layer.

        Args:
            coverage_data: Parsed coverage.json data
            layer_name: Layer name (services, clients, commands)

        Returns:
            LayerCoverage for the specified layer
        """
        layer_path = f"src/vibe3/{layer_name}"
        covered_lines = 0
        total_lines = 0

        # Iterate through files in coverage data
        files = coverage_data.get("files", {})
        for file_path, file_data in files.items():
            if not file_path.startswith(layer_path):
                continue

            summary = file_data.get("summary", {})
            covered_lines += summary.get("covered_lines", 0)
            total_lines += summary.get("num_statements", 0)

        # Calculate percentage
        coverage_percent = (
            (covered_lines / total_lines * 100) if total_lines > 0 else 0.0
        )

        return LayerCoverage(
            layer_name=layer_name,
            covered_lines=covered_lines,
            total_lines=total_lines,
            coverage_percent=coverage_percent,
            threshold=self.thresholds.get(layer_name, 80),
        )
