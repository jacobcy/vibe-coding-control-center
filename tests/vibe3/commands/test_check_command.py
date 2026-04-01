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
        from vibe3.services.check_service import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="fix_all", success=True, summary="All checks passed", details={}
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "All checks passed" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_with_issues(self, mock_service_class):
        """Test check command when issues found."""
        from vibe3.services.check_service import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="fix_all",
            success=False,
            summary="Issues found for branch 'task/demo'",
            details={"failed": ["task/demo: PR mismatch"]},
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check"])

        assert result.exit_code != 0
        assert "✗" in result.output
        assert "Issues found" in result.output
        assert "task/demo: PR mismatch" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_init_shows_unresolvable_details(self, mock_service_class):
        """Test --init mode prints unresolvable branch details."""
        from vibe3.services.check_service import ExecuteCheckResult

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

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_fix_all_output(self, mock_service_class):
        """Test check command summary output."""
        from vibe3.services.check_service import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.execute_check.return_value = ExecuteCheckResult(
            mode="fix_all",
            success=True,
            summary="All 3 fixable issues resolved",
            details={"fixed": 3},
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "Fixed: 3 flows" in result.output
        mock_service.execute_check.assert_called_once_with("fix_all")
