"""Integration tests for Check command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestCheckCommand:
    """Tests for check CLI command."""

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_valid(self, mock_service_class):
        """Test check command when all checks pass."""
        from vibe3.services.check_service import CheckResult

        mock_service = MagicMock()
        mock_service.verify_current_flow.return_value = CheckResult(
            is_valid=True, issues=[]
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "All checks passed" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_with_issues(self, mock_service_class):
        """Test check command when issues found."""
        from vibe3.services.check_service import CheckResult

        mock_service = MagicMock()
        mock_service.verify_current_flow.return_value = CheckResult(
            is_valid=False,
            issues=["Issue 1: Missing flow", "Issue 2: PR mismatch"],
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
        from vibe3.services.check_service import CheckResult, FixResult

        mock_service = MagicMock()
        mock_service.verify_current_flow.return_value = CheckResult(
            is_valid=False,
            issues=["Issue 1: Missing flow"],
        )
        mock_service.auto_fix.return_value = FixResult(success=True, error=None)
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["check", "--fix"])

        assert result.exit_code == 0
        assert "Auto-fixed" in result.output
        mock_service.auto_fix.assert_called_once()