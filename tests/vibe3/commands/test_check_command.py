"""Integration tests for Check command."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@dataclass
class _InvalidFlowResult:
    branch: str
    issues: list[str]


class TestCheckCommand:
    """Tests for check CLI command."""

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_valid(self, mock_service_class):
        """Test check command when all checks pass."""
        from vibe3.services.check_execute_mixin import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="default", success=True, summary="All checks passed"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "All checks passed" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_with_issues(self, mock_service_class):
        """Test check command when issues found."""
        from vibe3.services.check_execute_mixin import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="default",
            success=False,
            summary="Issues found for branch 'task/demo'",
            details={"issues": ["Issue 1: Missing flow", "Issue 2: PR mismatch"]},
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check"])

        assert result.exit_code != 0
        assert "✗" in result.output
        assert "Issues found" in result.output
        assert "Issue 1: Missing flow" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_with_fix(self, mock_service_class):
        """Test check command with --fix option."""
        from vibe3.services.check_execute_mixin import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="fix", success=True, summary="All issues fixed"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check", "--fix"])

        assert result.exit_code == 0
        assert "All issues fixed" in result.output
        mock_service.execute_check.assert_called_once_with("fix")

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_all_shows_per_flow_details(self, mock_service_class):
        """Test --all mode prints per-flow issue details."""
        from vibe3.services.check_execute_mixin import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="all",
            success=False,
            summary="1/2 flows have issues",
            details={
                "invalid": [
                    _InvalidFlowResult(
                        branch="task/demo",
                        issues=["Issue 1: Missing flow", "Issue 2: PR mismatch"],
                    )
                ]
            },
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check", "--all"])

        assert result.exit_code != 0
        assert "[task/demo]" in result.output
        assert "Issue 1: Missing flow" in result.output
        assert "Issue 2: PR mismatch" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_init_shows_unresolvable_details(self, mock_service_class):
        """Test --init mode prints unresolvable branch details."""
        from vibe3.services.check_execute_mixin import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="init",
            success=True,
            summary="Done  total=2  updated=1  skipped=1",
            details={"unresolvable": ["task/no-linked-issue"]},
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check", "--init"])

        assert result.exit_code == 0
        assert "Scanning merged PRs to back-fill task_issue_number" in result.output
        assert "Unresolvable (1 branches" in result.output
        assert "task/no-linked-issue" in result.output
