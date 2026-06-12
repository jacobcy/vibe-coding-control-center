"""Coverage service for running pytest with coverage analysis."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.models import CoverageReport, LayerCoverage


class CoverageService:
    """Service for running and analyzing test coverage by architectural layer."""

    def __init__(
        self,
        thresholds: dict[str, int] | None = None,
        project_root: Path | None = None,
    ):
        """Initialize coverage service.

        Args:
            thresholds: Custom coverage thresholds per layer.
                        If None, reads from config/v3/settings.yaml.
            project_root: Project root directory (defaults to cwd)
        """
        if thresholds is not None:
            self.thresholds = thresholds
        else:
            self.thresholds = self._load_thresholds_from_config()
        self.project_root = project_root or Path.cwd()

    @staticmethod
    def _load_thresholds_from_config() -> dict[str, int]:
        """Load coverage thresholds from configuration.

        Returns:
            Dict of layer name -> threshold percentage
        """
        from vibe3.config import get_config

        config = get_config()
        tc = config.quality.test_coverage
        return {
            "services": tc.services,
            "clients": tc.clients,
            "commands": tc.commands,
        }

    @staticmethod
    def _categorize_by_layer(
        coverage_data: dict[str, Any],
        layer_names: tuple[str, ...],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Pre-categorize coverage files by architectural layer in one pass.

        Returns:
            Dict mapping layer_name -> {file_path: file_data} for files
            whose path starts with f"src/vibe3/{layer_name}".
        """
        categorized: dict[str, dict[str, dict[str, Any]]] = {
            name: {} for name in layer_names
        }
        for file_path, file_data in coverage_data.get("files", {}).items():
            for layer_name in layer_names:
                if file_path.startswith(f"src/vibe3/{layer_name}"):
                    categorized[layer_name][file_path] = file_data
                    break  # each file belongs to at most one layer
        return categorized

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

        # 2. Pre-categorize files by layer (single pass)
        layers = ("services", "clients", "commands")
        categorized = self._categorize_by_layer(coverage_data, layers)

        # 3. Analyze by layer (using pre-categorized files)
        services_cov = self._analyze_layer(
            coverage_data, "services", categorized["services"]
        )
        clients_cov = self._analyze_layer(
            coverage_data, "clients", categorized["clients"]
        )
        commands_cov = self._analyze_layer(
            coverage_data, "commands", categorized["commands"]
        )

        # 4. Build report
        report = CoverageReport(
            services=services_cov,
            clients=clients_cov,
            commands=commands_cov,
        )

        logger.info(
            f"Coverage check complete: {report.overall_percent:.1f}% overall, "
            f"all_passing={report.all_passing}"
        )

        return report

    def _run_pytest_cov(self) -> dict[str, Any]:
        """Run pytest with --cov --cov-json and parse output.

        Output is saved to .agent/reports/coverage/<branch>/coverage.json

        Returns:
            Parsed coverage data from coverage.json

        Raises:
            RuntimeError: If pytest or coverage run fails
        """
        from vibe3.clients import GitClient

        # Always use branch for paths (branch is always available)
        git = GitClient()
        current_branch = git.get_current_branch()
        reports_dir = (
            self.project_root
            / ".agent"
            / "reports"
            / "coverage"
            / current_branch.replace("/", "-")
        )
        reports_dir.mkdir(parents=True, exist_ok=True)
        cov_file = reports_dir / "coverage.json"

        # Remove old coverage.json to prevent reusing stale data
        if cov_file.exists():
            cov_file.unlink()
            logger.debug(f"Removed old {cov_file}")

        cmd = [
            "uv",
            "run",
            "pytest",
            "--cov=src/vibe3",
            f"--cov-report=json:{cov_file}",
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

            # Check pytest return code
            if result.returncode != 0:
                error_msg = f"pytest failed with return code {result.returncode}"
                if result.stdout:
                    error_msg += f"\nstdout:\n{result.stdout}"
                if result.stderr:
                    error_msg += f"\nstderr:\n{result.stderr}"
                raise RuntimeError(error_msg)

            # Parse coverage.json
            if not cov_file.exists():
                raise RuntimeError(f"coverage.json not generated at {cov_file}")

            with open(cov_file) as f:
                data: dict[str, Any] = json.load(f)

            logger.info(f"Coverage report saved to {cov_file}")
            return data

        except Exception as e:
            logger.error(f"Failed to run coverage: {e}")
            raise RuntimeError(f"Coverage run failed: {e}") from e

    def _analyze_layer(
        self,
        coverage_data: dict[str, Any],
        layer_name: str,
        _layer_files: dict[str, dict[str, Any]] | None = None,
    ) -> LayerCoverage:
        """Analyze coverage for a specific architectural layer.

        Args:
            coverage_data: Parsed coverage.json data (unused when _layer_files is given)
            layer_name: Layer name (services, clients, commands)
            _layer_files: Pre-categorized files for this layer (optional optimization).
                When provided, coverage_data is not re-inspected.
                When None, falls back to independent re-filtering for
                backward compatibility.

        Returns:
            LayerCoverage for the specified layer
        """
        if _layer_files is not None:
            files = _layer_files
        else:
            # Fallback path: re-filter coverage_data by layer for backward
            # compatibility with direct callers. In production, run_coverage_check
            # always provides _layer_files; this path exists for testability.
            layer_path = f"src/vibe3/{layer_name}"
            files = {
                fp: fd
                for fp, fd in coverage_data.get("files", {}).items()
                if fp.startswith(layer_path)
            }

        covered_lines = 0
        total_lines = 0

        # Iterate through files
        for file_data in files.values():
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
