"""Tests for internal commands (hidden from users)."""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.cli import app as cli_app

runner = CliRunner()


def test_internal_manager_dispatch():
    """测试 internal manager 命令参数解析和调用."""
    with patch("vibe3.manager.manager_run_service.run_manager_issue_mode") as mock_run:
        result = runner.invoke(cli_app, ["internal", "manager", "123", "--no-async"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            issue_number=123,
            dry_run=False,
            async_mode=False,  # --no-async
            fresh_session=False,
        )


def test_internal_manager_with_options():
    """测试 internal manager 命令支持所有选项."""
    with patch("vibe3.manager.manager_run_service.run_manager_issue_mode") as mock_run:
        result = runner.invoke(
            cli_app,
            [
                "internal",
                "manager",
                "456",
                "--no-async",
                "--dry-run",
                "--fresh-session",
            ],
        )

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            issue_number=456,
            dry_run=True,
            async_mode=False,
            fresh_session=True,
        )


def test_internal_apply_dispatch():
    """测试 internal apply 命令参数解析和调用."""
    with patch(
        "vibe3.orchestra.supervisor_run_service.run_supervisor_mode"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "apply", "/path/to/supervisor.md", "--no-async"],
        )

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            supervisor_file="/path/to/supervisor.md",
            issue_number=None,
            dry_run=False,
            async_mode=False,
        )


def test_internal_apply_with_issue():
    """测试 internal apply 命令支持 --issue 选项."""
    with patch(
        "vibe3.orchestra.supervisor_run_service.run_supervisor_mode"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            [
                "internal",
                "apply",
                "/path/to/supervisor.md",
                "--issue",
                "789",
                "--no-async",
            ],
        )

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            supervisor_file="/path/to/supervisor.md",
            issue_number=789,
            dry_run=False,
            async_mode=False,
        )


def test_internal_hidden_from_help():
    """测试 internal 命令对用户不可见."""
    result = runner.invoke(cli_app, ["--help"])
    # internal 命令应该出现在帮助信息中,但标注为 hidden
    assert "internal" not in result.stdout or "Internal" in result.stdout
