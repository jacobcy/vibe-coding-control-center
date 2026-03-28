"""Integration tests for Check command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


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
