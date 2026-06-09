"""Tests for check command.

Merged from test_check_branch.py + test_check_command.py.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.check import app as check_app
from vibe3.commands.check_support import ExecuteCheckResult

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


def _make_remote_result(
    *,
    success: bool,
    summary: str,
    checked_count: int = 0,
    anomalies: list | None = None,
    removed_count: int = 0,
    added_count: int = 0,
    dry_run: bool = True,
) -> ExecuteCheckResult:
    """Helper to create an ExecuteCheckResult for remote check tests."""
    return ExecuteCheckResult(
        mode="remote",
        success=success,
        summary=summary,
        details={
            "checked_count": checked_count,
            "anomalies": anomalies or [],
            "removed_count": removed_count,
            "added_count": added_count,
            "errors": [],
            "dry_run": dry_run,
        },
    )


@patch("vibe3.commands.check.execute_remote_check")
def test_check_remote_dry_run(mock_check):
    """--dry-run flag is passed to execute_remote_check."""
    mock_check.return_value = _make_remote_result(
        success=True,
        summary="Checked 0 issues, no anomalies found",
        checked_count=0,
    )
    result = runner.invoke(app, ["check", "remote", "--dry-run"])

    assert result.exit_code == 0
    mock_check.assert_called_once_with(dry_run=True, show_progress=True)


@patch("vibe3.commands.check.execute_remote_check")
def test_check_remote_applies_fixes(mock_check):
    """Without --dry-run, execute_remote_check is called with dry_run=False."""
    mock_check.return_value = _make_remote_result(
        success=True,
        summary="Checked 0 issues, no anomalies found",
        checked_count=0,
        dry_run=False,
    )
    result = runner.invoke(app, ["check", "remote"])

    assert result.exit_code == 0
    mock_check.assert_called_once_with(dry_run=False, show_progress=True)


@patch("vibe3.commands.check.execute_remote_check")
def test_check_remote_with_anomalies(mock_check):
    """Output groups anomalies by rule when anomalies are found."""
    mock_check.return_value = _make_remote_result(
        success=False,
        summary="Checked 342 issues, found 2 anomalies",
        checked_count=342,
        anomalies=[
            {
                "issue_number": 123,
                "rule": "roadmap_conflict",
                "removed": ["state/claimed"],
                "added": [],
            },
            {
                "issue_number": 456,
                "rule": "roadmap_conflict",
                "removed": ["state/in-progress", "state/blocked"],
                "added": [],
            },
            {
                "issue_number": 789,
                "rule": "multi_state",
                "removed": ["state/review"],
                "added": [],
            },
        ],
        removed_count=4,
        added_count=0,
        dry_run=True,
    )
    result = runner.invoke(app, ["check", "remote", "--dry-run"])

    assert result.exit_code != 0
    assert "roadmap_conflict" in result.output
    assert "multi_state" in result.output
    assert "#123" in result.output
    assert "#456" in result.output
    assert "#789" in result.output
    assert "state/claimed" in result.output
    assert "state/in-progress" in result.output
    assert "state/blocked" in result.output
    assert "state/review" in result.output
    assert "Would remove" in result.output
    assert "4 label(s)" in result.output
    # No literal Rich markup tags
    assert "[green]" not in result.output
    assert "[bold]" not in result.output


@patch("vibe3.commands.check.execute_remote_check")
def test_check_remote_no_anomalies(mock_check):
    """Clean result shows 'no anomalies' message."""
    mock_check.return_value = _make_remote_result(
        success=True,
        summary="Checked 342 issues, no anomalies found",
        checked_count=342,
    )
    result = runner.invoke(app, ["check", "remote", "--dry-run"])

    assert result.exit_code == 0
    assert "no anomalies" in result.output


@patch("vibe3.commands.check.CheckService")
def test_check_backward_compat(mock_service_class):
    """vibe3 check (no subcommand) still routes to legacy behavior."""
    from vibe3.commands.check_support import ExecuteCheckResult

    mock_service = MagicMock()
    result_obj = ExecuteCheckResult(
        mode="fix_all", success=True, summary="All checks passed", details={}
    )
    mock_service_class.return_value = mock_service
    with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
        result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "All checks passed" in result.output


@patch("vibe3.commands.check.CheckService")
def test_check_local_subcommand(mock_service_class):
    """vibe3 check local invokes same path as vibe3 check."""
    from vibe3.commands.check_support import ExecuteCheckResult

    mock_service = MagicMock()
    result_obj = ExecuteCheckResult(
        mode="fix_all", success=True, summary="All checks passed", details={}
    )
    mock_service_class.return_value = mock_service
    with patch("vibe3.commands.check.execute_check_mode", return_value=result_obj):
        result = runner.invoke(app, ["check", "local"])

    assert result.exit_code == 0
    assert "All checks passed" in result.output


# ==============================================================================
# _audit_single_issue integration tests
# ==============================================================================


class TestAuditSingleIssue:
    """Direct tests for _audit_single_issue composition logic."""

    def test_manager_assignee_triggers_rules(self) -> None:
        """Manager-assigned issue with execution state triggers Rule 3."""
        from vibe3.commands.check_support import _audit_single_issue

        issue = {
            "number": 42,
            "labels": [{"name": "state/in-progress"}],
            "assignees": [{"login": "vibe-manager-agent"}],
        }
        result = _audit_single_issue(
            issue=issue,
            local_issue_numbers=set(),  # no local flow
            manager_usernames=("vibe-manager-agent",),
        )

        assert len(result) == 1
        assert result[0]["rule"] == "orphan_execution"
        assert result[0]["issue_number"] == 42

    def test_non_manager_assignee_skips_rules_3_4(self) -> None:
        """Non-manager issue does NOT trigger Rule 3."""
        from vibe3.commands.check_support import _audit_single_issue

        issue = {
            "number": 43,
            "labels": [{"name": "state/in-progress"}],
            "assignees": [{"login": "stranger"}],
        }
        result = _audit_single_issue(
            issue=issue,
            local_issue_numbers=set(),
            manager_usernames=("vibe-manager-agent",),
        )

        assert result == []  # no anomalies for non-manager

    def test_orchestra_governed_without_manager_assignee_no_rule_3(self) -> None:
        """orchestra-governed label alone does NOT make is_manager_issue=True."""
        from vibe3.commands.check_support import _audit_single_issue

        issue = {
            "number": 44,
            "labels": [{"name": "orchestra-governed"}, {"name": "state/in-progress"}],
            "assignees": [],  # no manager assignee
        }
        result = _audit_single_issue(
            issue=issue,
            local_issue_numbers=set(),
            manager_usernames=("vibe-manager-agent",),
        )

        # Rule 3 should NOT fire (not a manager issue)
        rules = [r["rule"] for r in result]
        assert "orphan_execution" not in rules

    def test_has_local_flow_prevents_rule_3(self) -> None:
        """Issue with local flow does NOT trigger orphan execution."""
        from vibe3.commands.check_support import _audit_single_issue

        issue = {
            "number": 42,
            "labels": [{"name": "state/in-progress"}],
            "assignees": [{"login": "vibe-manager-agent"}],
        }
        result = _audit_single_issue(
            issue=issue,
            local_issue_numbers={42},  # has local flow
            manager_usernames=("vibe-manager-agent",),
        )

        assert result == []

    def test_no_number_returns_empty(self) -> None:
        """Issue without number returns empty list."""
        from vibe3.commands.check_support import _audit_single_issue

        issue = {"labels": [{"name": "state/ready"}], "assignees": []}
        result = _audit_single_issue(
            issue=issue,
            local_issue_numbers=set(),
            manager_usernames=(),
        )

        assert result == []
