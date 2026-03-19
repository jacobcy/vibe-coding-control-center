"""Tests for vibe inspect metrics subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def _mock_metrics():
    """Minimal MetricsReport mock."""
    from vibe3.services.metrics_service import LayerMetrics, MetricsReport

    layer = LayerMetrics(
        total_loc=100,
        limit_total=5000,
        max_file_loc=50,
        limit_file_default=200,
        limit_file_max=300,
        file_count=5,
        files=[],
    )
    return MetricsReport(shell=layer, python=layer)


def test_inspect_metrics_no_args():
    """metrics 无需参数，应正常运行。"""
    with patch(
        "vibe3.commands.inspect.metrics_service.collect_metrics",
        return_value=_mock_metrics(),
    ):
        result = runner.invoke(app, ["metrics"])
    assert result.exit_code == 0
    assert "Shell" in result.output or "Python" in result.output


def test_inspect_metrics_json():
    with patch(
        "vibe3.commands.inspect.metrics_service.collect_metrics",
        return_value=_mock_metrics(),
    ):
        result = runner.invoke(app, ["metrics", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "shell" in data
    assert "python" in data


def test_inspect_metrics_help():
    result = runner.invoke(app, ["metrics", "--help"])
    assert result.exit_code == 0
