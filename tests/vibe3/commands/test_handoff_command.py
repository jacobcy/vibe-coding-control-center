"""Integration tests for Handoff commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestHandoffCommands:
    """Tests for handoff CLI commands."""

    @patch("vibe3.commands.handoff.HandoffService")
    def test_handoff_init_command(self, mock_service_class):
        """Test handoff init command."""
        mock_service = MagicMock()
        mock_service.ensure_current_handoff.return_value = "/path/to/current.md"
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["handoff", "init"])

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Handoff file ready" in result.output
        mock_service.ensure_current_handoff.assert_called_once()

    @patch("vibe3.commands.handoff.HandoffService")
    def test_handoff_show_command(self, mock_service_class):
        """Test handoff show command."""
        mock_service = MagicMock()
        mock_service.read_current_handoff.return_value = "# Handoff content"
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["handoff", "show"])

        assert result.exit_code == 0
        assert "# Handoff content" in result.output
        mock_service.read_current_handoff.assert_called_once()

    @patch("vibe3.commands.handoff.HandoffService")
    def test_handoff_plan_command(self, mock_service_class):
        """Test handoff plan command."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "plan",
                "docs/plans/test-plan.md",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Plan handoff recorded" in result.output
        mock_service.record_plan.assert_called_once_with(
            "docs/plans/test-plan.md", None, None, "claude/sonnet-4.6"
        )

    @patch("vibe3.commands.handoff.HandoffService")
    def test_handoff_report_command(self, mock_service_class):
        """Test handoff report command."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "report",
                "docs/reports/test-report.md",
                "--next-step",
                "Address feedback",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Report handoff recorded" in result.output
        mock_service.record_report.assert_called_once_with(
            "docs/reports/test-report.md",
            "Address feedback",
            None,
            "claude/sonnet-4.6",
        )

    @patch("vibe3.commands.handoff.HandoffService")
    def test_handoff_audit_command(self, mock_service_class):
        """Test handoff audit command."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "audit",
                "docs/audits/test-audit.md",
                "--blocked-by",
                "Waiting for review",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Audit handoff recorded" in result.output
        mock_service.record_audit.assert_called_once_with(
            "docs/audits/test-audit.md",
            None,
            "Waiting for review",
            "claude/sonnet-4.6",
        )

    @patch("vibe3.commands.handoff.HandoffService")
    def test_handoff_with_options(self, mock_service_class):
        """Test handoff commands with optional parameters."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "plan",
                "docs/plans/test-plan.md",
                "--next-step",
                "Start implementation",
                "--blocked-by",
                "API key needed",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        mock_service.record_plan.assert_called_once_with(
            "docs/plans/test-plan.md",
            "Start implementation",
            "API key needed",
            "claude/sonnet-4.6",
        )


class TestCheckCommand:
    """Tests for check CLI command."""

    @patch("vibe3.cli.CheckService")
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

    @patch("vibe3.cli.CheckService")
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

    @patch("vibe3.cli.CheckService")
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

        assert "Attempting auto-fix" in result.output
        assert "✓ Issues fixed" in result.output
        mock_service.auto_fix.assert_called_once()
