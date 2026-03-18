"""Tests for PR ready command - output formats and edge cases."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.pr import app

runner = CliRunner()


def test_pr_ready_coverage_exception_handling():
    """pr ready handles coverage check exceptions gracefully."""
    with patch(
        "vibe3.services.coverage_service.CoverageService"
    ) as mock_cov_service, patch(
        "vibe3.commands.pr_lifecycle.PRService"
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.side_effect = RuntimeError(
            "pytest failed"
        )
        mock_cov_service.return_value = mock_cov_instance

        result = runner.invoke(app, ["ready", "123", "--yes"])

        assert result.exit_code == 1
        assert (
            "Coverage check failed" in result.output
            or "coverage" in result.output.lower()
        )


def test_pr_ready_json_output(
    mock_pr_response, mock_coverage_all_passing, mock_inspect_passing
):
    """pr ready --json outputs JSON format."""
    with patch(
        "vibe3.services.coverage_service.CoverageService"
    ) as mock_cov_service, patch(
        "vibe3.commands.pr_lifecycle.PRService"
    ) as mock_pr_service, patch(
        "vibe3.commands.review_helpers.run_inspect_json",
        return_value=mock_inspect_passing,
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.return_value = mock_coverage_all_passing
        mock_cov_service.return_value = mock_cov_instance

        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        result = runner.invoke(app, ["ready", "123", "--yes", "--json"])

        assert result.exit_code == 0
        assert '"number": 123' in result.output
        assert '"title": "Test PR"' in result.output


def test_pr_ready_yaml_output(
    mock_pr_response, mock_coverage_all_passing, mock_inspect_passing
):
    """pr ready --yaml outputs YAML format."""
    with patch(
        "vibe3.services.coverage_service.CoverageService"
    ) as mock_cov_service, patch(
        "vibe3.commands.pr_lifecycle.PRService"
    ) as mock_pr_service, patch(
        "vibe3.commands.review_helpers.run_inspect_json",
        return_value=mock_inspect_passing,
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.return_value = mock_coverage_all_passing
        mock_cov_service.return_value = mock_cov_instance

        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        result = runner.invoke(app, ["ready", "123", "--yes", "--yaml"])

        assert result.exit_code == 0
        assert "number: 123" in result.output
        assert "title: Test PR" in result.output