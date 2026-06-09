"""Tests for check command.

Merged from test_check_branch.py + test_check_command.py.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.check import app as check_app

runner = CliRunner()


# ==============================================================================
# Branch parameter tests (from test_check_branch.py)
# ==============================================================================


def test_check_branch_mutually_exclusive_with_init() -> None:
    """--branch and --init should be mutually exclusive."""
    result = runner.invoke(check_app, ["--branch", "dev/test", "--init"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_check_branch_mutually_exclusive_with_clean_branch() -> None:
    """--branch and --clean-branch should be mutually exclusive."""
    result = runner.invoke(check_app, ["--branch", "dev/test", "--clean-branch"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


# ==============================================================================
# Check command integration tests (from test_check_command.py)
# ==============================================================================


@dataclass
class _InvalidFlowResult:
    branch: str
    issues: list[str]


class TestCheckCommand:
    """Tests for check CLI command."""

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_valid(self, mock_service_class):
        """Test check command when all checks pass."""
        from vibe3.commands.check_support import ExecuteCheckResult

        mock_service = MagicMock()
        result_obj = ExecuteCheckResult(
            mode="fix_all", success=True, summary="All checks passed", details={}
        )
        mock_service_class.return_value = mock_service
        with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "All checks passed" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_with_issues(self, mock_service_class):
        """Test check command when issues found."""
        from vibe3.commands.check_support import ExecuteCheckResult

        mock_service = MagicMock()
        result_obj = ExecuteCheckResult(
            mode="fix_all",
            success=False,
            summary="Issues found for branch 'task/demo'",
            details={"failed": ["task/demo: PR mismatch"]},
        )
        mock_service_class.return_value = mock_service
        with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
            result = runner.invoke(app, ["check"])

        assert result.exit_code != 0
        assert "✗" in result.output
        assert "Issues found" in result.output
        assert "task/demo: PR mismatch" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_init_shows_unresolvable_details(self, mock_service_class):
        """Test --init mode prints unresolvable branch details."""
        from vibe3.commands.check_support import ExecuteCheckResult

        mock_service = MagicMock()
        result_obj = ExecuteCheckResult(
            mode="init",
            success=True,
            summary="Done  total=2  updated=1  skipped=1",
            details={"unresolvable": ["task/no-linked-issue"]},
        )
        mock_service_class.return_value = mock_service
        with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
            result = runner.invoke(app, ["check", "--init"])

        assert result.exit_code == 0
        assert "Scanning merged PRs to back-fill task_issue_number" in result.output
        # Rich markup must be rendered, not printed literally (issue #2033)
        assert "Unresolvable (1 branches" in result.output
        assert "[yellow]" not in result.output
        assert "task/no-linked-issue" in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_fix_all_output(self, mock_service_class):
        """Test check command summary output."""
        from vibe3.commands.check_support import ExecuteCheckResult

        mock_service = MagicMock()
        mock_service.verify_all_flows.return_value = []
        result_obj = ExecuteCheckResult(
            mode="fix_all",
            success=True,
            summary="All 3 fixable issues resolved",
            details={"fixed": 3},
        )
        mock_service_class.return_value = mock_service
        with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        # Rich markup must be rendered, not printed literally (issue #2033)
        assert "Fixed: 3 flows" in result.output
        assert "[green]" not in result.output

    @patch("vibe3.commands.check.CheckService")
    def test_check_command_clean_branch_renders_markup(self, mock_service_class):
        """clean_branch details must render Rich markup, not show literal tags."""
        from vibe3.commands.check_support import ExecuteCheckResult

        mock_service_class.return_value = MagicMock()
        result_obj = ExecuteCheckResult(
            mode="clean_branch",
            success=True,
            summary="Cleaned 1 aborted flows",
            details={
                "cleaned": ["task/issue-1"],
                "local_branches": {
                    "cleaned": ["feature-x"],
                    "skipped_active_flow": ["dev/issue-2"],
                    "failed": ["feature-y: boom"],
                },
            },
        )
        with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
            result = runner.invoke(app, ["check", "--clean-branch"], input="y\n")

        assert result.exit_code == 0
        # No literal Rich markup tags leak into output
        assert "[green]" not in result.output
        assert "[red]" not in result.output
        assert "[cyan]" not in result.output
        # Rendered content present
        assert "Cleaned" in result.output
        assert "feature-x" in result.output
        assert "Local branches failed" in result.output
        assert "feature-y: boom" in result.output


# ==============================================================================
# Remote check tests
# ==============================================================================


@patch("vibe3.commands.check.execute_remote_check")
def test_check_remote_dry_run(mock_remote):
    """--dry-run flag is passed to execute_remote_check."""
    from vibe3.commands.check_support import ExecuteCheckResult

    mock_remote.return_value = ExecuteCheckResult(
        mode="remote",
        success=True,
        summary="Checked 0 issues, found 0 anomalies",
        details={"anomalies": [], "removed": 0, "added": 0, "dry_run": True},
    )
    result = runner.invoke(app, ["check", "remote", "--dry-run"])

    assert result.exit_code == 0
    mock_remote.assert_called_once_with(dry_run=True)


@patch("vibe3.commands.check.execute_remote_check")
def test_check_remote_with_anomalies_display(mock_remote):
    """Display formatting: anomalies grouped by rule with actions and totals."""
    from vibe3.commands.check_support import ExecuteCheckResult
    from vibe3.services.shared import LabelAnomaly

    anomalies = [
        LabelAnomaly(
            issue_number=123,
            rule="multi_state",
            removed=["state/in-progress"],
            added=["state/review"],
        ),
        LabelAnomaly(
            issue_number=456,
            rule="orphan_execution, multi_state",
            removed=["state/blocked"],
            added=[],
        ),
    ]
    mock_remote.return_value = ExecuteCheckResult(
        mode="remote",
        success=True,
        summary="Checked 100 issues, found 2 anomalies",
        details={"anomalies": anomalies, "removed": 0, "added": 0, "dry_run": True},
    )
    result = runner.invoke(app, ["check", "remote", "--dry-run"])

    assert result.exit_code == 0
    assert "Checked 100 issues, found 2 anomalies" in result.output
    assert "multi_state" in result.output
    assert "orphan_execution" in result.output
    assert "#123" in result.output
    assert "#456" in result.output
    assert "remove state/in-progress" in result.output
    assert "add state/review" in result.output
    assert "remove state/blocked" in result.output
    assert "Total: 0 labels removed, 0 labels added" in result.output
    assert "[DRY RUN] No labels were modified" in result.output


@patch("vibe3.commands.check.CheckService")
def test_check_backward_compat(mock_service_class):
    """vibe3 check (no subcommand) still routes to legacy behavior."""
    from vibe3.commands.check_support import ExecuteCheckResult

    mock_service_class.return_value = MagicMock()
    result_obj = ExecuteCheckResult(
        mode="fix_all", success=True, summary="All checks passed", details={}
    )
    with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
        result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "All checks passed" in result.output


@patch("vibe3.commands.check.CheckService")
def test_check_local_subcommand(mock_service_class):
    """vibe3 check local invokes same path as vibe3 check."""
    from vibe3.commands.check_support import ExecuteCheckResult

    mock_service_class.return_value = MagicMock()
    result_obj = ExecuteCheckResult(
        mode="fix_all", success=True, summary="All checks passed", details={}
    )
    with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
        result = runner.invoke(app, ["check", "local"])

    assert result.exit_code == 0
    assert "All checks passed" in result.output
