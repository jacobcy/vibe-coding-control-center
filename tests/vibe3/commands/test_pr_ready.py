"""Tests for PR ready command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.pr import app
from vibe3.services.pr_ready_usecase import PrReadyAbortedError

runner = CliRunner()


def test_pr_ready_without_arg_resolves_pr_from_flow_state(mock_pr_response):
    """pr ready (missing PR number) should resolve from current flow PR."""
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch("vibe3.commands.pr_lifecycle.FlowService") as mock_flow_service,
        patch(
            "vibe3.commands.pr_lifecycle._build_pr_ready_usecase"
        ) as mock_build_usecase,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.store.get_flow_state.return_value = {"pr_number": 123}
        mock_pr_service.return_value = mock_pr_instance

        mock_flow_instance = MagicMock()
        mock_flow_instance.get_current_branch.return_value = "task/demo"
        mock_flow_service.return_value = mock_flow_instance

        mock_usecase = MagicMock()
        mock_usecase.mark_ready.return_value = mock_pr_response
        mock_build_usecase.return_value = mock_usecase

        result = runner.invoke(app, ["ready", "--yes"])

        assert result.exit_code == 0
        mock_usecase.mark_ready.assert_called_once_with(pr_number=123, yes=True)


def test_pr_ready_without_arg_and_no_current_pr_shows_error():
    """pr ready (missing PR number) should fail with clear hint when no PR found."""
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch("vibe3.commands.pr_lifecycle.FlowService") as mock_flow_service,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.store.get_flow_state.return_value = {}
        mock_pr_instance.get_pr.return_value = None
        mock_pr_service.return_value = mock_pr_instance

        mock_flow_instance = MagicMock()
        mock_flow_instance.get_current_branch.return_value = "task/no-pr"
        mock_flow_service.return_value = mock_flow_instance

        result = runner.invoke(app, ["ready", "--yes"])

        assert result.exit_code == 1
        assert "No PR found for current branch 'task/no-pr'" in result.output
        assert "vibe3 pr ready <PR_NUMBER>" in result.output


def test_pr_ready_help():
    """pr ready --help shows usage."""
    result = runner.invoke(app, ["ready", "--help"])
    assert result.exit_code == 0
    assert "PR number" in result.output
    # Check for -yes or --yes (may have ANSI color codes)
    assert "-yes" in result.output or "--yes" in result.output


def test_pr_ready_user_abort_exits_zero():
    """pr ready confirmation abort should exit 0 without string-matching errors."""
    aborted_usecase = MagicMock()
    aborted_usecase.mark_ready.side_effect = PrReadyAbortedError("aborted by user")

    with patch(
        "vibe3.commands.pr_lifecycle._build_pr_ready_usecase",
        return_value=aborted_usecase,
    ):
        result = runner.invoke(app, ["ready", "123"])

    assert result.exit_code == 0


def test_pr_ready_with_coverage_passing(
    mock_pr_response, mock_coverage_all_passing, mock_inspect_passing
):
    """pr ready with coverage gate passing."""
    with (
        patch("vibe3.analysis.coverage_service.CoverageService") as mock_cov_service,
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch(
            "vibe3.agents.review_pipeline_helpers.run_inspect_json",
            return_value=mock_inspect_passing,
        ),
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.return_value = mock_coverage_all_passing
        mock_cov_service.return_value = mock_cov_instance

        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        result = runner.invoke(app, ["ready", "123", "--yes"])

        assert result.exit_code == 0
        # With --yes, coverage gate is bypassed
        assert "Skipping coverage gate" in result.output


def test_pr_ready_prints_risk_reason_and_breakdown(
    mock_pr_response, mock_coverage_all_passing
):
    """pr ready should print explainable risk details."""
    inspect_result = {
        "score": {
            "score": 9,
            "level": "CRITICAL",
            "block": True,
            "reason": "触达关键路径且影响范围较大，达到阻断阈值",
            "trigger_factors": ["changed_files(+2)", "critical_path_touch(+2)"],
            "recommendations": ["拆分 PR 以降低影响面", "补充关键路径回归测试"],
            "breakdown": {
                "changed_files": 2,
                "critical_path_touch": 2,
            },
        }
    }
    with (
        patch("vibe3.analysis.coverage_service.CoverageService") as mock_cov_service,
        patch(
            "vibe3.agents.review_pipeline_helpers.run_inspect_json",
            return_value=inspect_result,
        ),
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.return_value = mock_coverage_all_passing
        mock_cov_service.return_value = mock_cov_instance

        result = runner.invoke(app, ["ready", "123"])

        assert result.exit_code == 1
        assert "触达关键路径且影响范围较大" in result.output
        assert "changed_files(+2)" in result.output
        assert "补充关键路径回归测试" in result.output


def test_pr_ready_with_coverage_failing(mock_coverage_failing):
    """pr ready with coverage gate failing and no --yes → exit 1."""
    with (
        patch("vibe3.analysis.coverage_service.CoverageService") as mock_cov_service,
        patch("vibe3.commands.pr_lifecycle.PRService"),
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.return_value = mock_coverage_failing
        mock_cov_service.return_value = mock_cov_instance

        # Without --yes, coverage gate failure should cause exit 1
        result = runner.invoke(app, ["ready", "123"])

        assert result.exit_code == 1
        assert "Coverage gate failed" in result.output
        assert "70.0%" in result.output


def test_pr_ready_yes_bypass_coverage(mock_pr_response, mock_inspect_passing):
    """pr ready --yes bypasses coverage gate."""
    with (
        patch("vibe3.analysis.coverage_service.CoverageService"),
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch(
            "vibe3.agents.review_pipeline_helpers.run_inspect_json",
            return_value=mock_inspect_passing,
        ),
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        result = runner.invoke(app, ["ready", "123", "--yes"])

        assert result.exit_code == 0
        assert "Skipping coverage gate (--yes)" in result.output


def test_pr_ready_coverage_exception_handling():
    """pr ready handles coverage check exceptions gracefully."""
    with (
        patch("vibe3.analysis.coverage_service.CoverageService") as mock_cov_service,
        patch("vibe3.commands.pr_lifecycle.PRService"),
    ):
        mock_cov_instance = MagicMock()
        mock_cov_instance.run_coverage_check.side_effect = RuntimeError("pytest failed")
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
    with (
        patch("vibe3.analysis.coverage_service.CoverageService") as mock_cov_service,
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch(
            "vibe3.agents.review_pipeline_helpers.run_inspect_json",
            return_value=mock_inspect_passing,
        ),
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
    with (
        patch("vibe3.analysis.coverage_service.CoverageService") as mock_cov_service,
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch(
            "vibe3.agents.review_pipeline_helpers.run_inspect_json",
            return_value=mock_inspect_passing,
        ),
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
