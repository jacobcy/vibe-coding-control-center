"""Tests for PR ready command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.pr import app

runner = CliRunner()


def test_pr_ready_missing_arg_shows_error():
    """pr ready (missing PR number) → friendly error."""
    result = runner.invoke(app, ["ready"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_pr_ready_help():
    """pr ready --help shows usage."""
    result = runner.invoke(app, ["ready", "--help"])
    assert result.exit_code == 0
    assert "PR number" in result.output
    assert "--force" in result.output
    assert "--skip-coverage" in result.output


def test_pr_ready_with_coverage_passing(
    mock_pr_response, mock_coverage_all_passing, mock_inspect_passing
):
    """pr ready with coverage gate passing."""
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

        result = runner.invoke(app, ["ready", "123", "--yes"])

        assert result.exit_code == 0
        assert "Coverage gate passed" in result.output
        assert "85.0%" in result.output or "86.8%" in result.output


def test_pr_ready_with_coverage_failing(mock_coverage_failing):
    """pr ready with coverage gate failing → exit 1."""
    with patch(
        "vibe3.services.coverage_service.CoverageService"
    ) as mock_cov_service, patch(
        "vibe3.commands.pr_lifecycle.PRService"
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.return_value = mock_coverage_failing
        mock_cov_service.return_value = mock_cov_instance

        result = runner.invoke(app, ["ready", "123", "--yes"])

        assert result.exit_code == 1
        assert "Coverage gate failed" in result.output
        assert "70.0%" in result.output


def test_pr_ready_skip_coverage(mock_pr_response, mock_inspect_passing):
    """pr ready --skip-coverage skips coverage gate."""
    with patch(
        "vibe3.services.coverage_service.CoverageService"
    ) as mock_cov_service, patch(
        "vibe3.commands.pr_lifecycle.PRService"
    ) as mock_pr_service, patch(
        "vibe3.commands.review_helpers.run_inspect_json",
        return_value=mock_inspect_passing,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        result = runner.invoke(app, ["ready", "123", "--yes", "--skip-coverage"])

        assert result.exit_code == 0
        assert "Skipping coverage gate" in result.output
        mock_cov_service.assert_not_called()


def test_pr_ready_force_skips_all_gates(mock_pr_response):
    """pr ready --force skips all quality gates."""
    with patch(
        "vibe3.services.coverage_service.CoverageService"
    ) as mock_cov_service, patch(
        "vibe3.commands.pr_lifecycle.PRService"
    ) as mock_pr_service:
        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        result = runner.invoke(app, ["ready", "123", "--yes", "--force"])

        assert result.exit_code == 0
        assert "跳过质量门禁" in result.output
        mock_cov_service.assert_not_called()


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