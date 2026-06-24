"""Tests for internal commands (hidden from users)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app as cli_app

runner = CliRunner()


# Guard tests: verify _require_async_child behavior


def test_internal_manager_guard_blocks_direct_call(monkeypatch):
    """Invoke internal manager without env var and without --yes → exit 1."""
    monkeypatch.delenv("VIBE3_ASYNC_CHILD", raising=False)
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(cli_app, ["internal", "manager", "123", "--no-async"])
        assert result.exit_code == 1
        mock_run.assert_not_called()


def test_internal_manager_guard_allows_yes(monkeypatch):
    """Invoke internal manager --yes without VIBE3_ASYNC_CHILD → exit 0."""
    monkeypatch.delenv("VIBE3_ASYNC_CHILD", raising=False)
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app, ["internal", "manager", "123", "--no-async", "--yes"]
        )
        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123


def test_internal_manager_guard_passes_with_env(monkeypatch):
    """Set VIBE3_ASYNC_CHILD=1 → exit 0 without --yes."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(cli_app, ["internal", "manager", "123", "--no-async"])
        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123


def test_internal_apply_guard_blocks_direct_call(monkeypatch):
    """Invoke internal apply without VIBE3_ASYNC_CHILD and without --yes → exit 1."""
    monkeypatch.delenv("VIBE3_ASYNC_CHILD", raising=False)
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(cli_app, ["internal", "apply", "42", "--no-async"])
        assert result.exit_code == 1
        mock_run.assert_not_called()


def test_internal_governance_guard_blocks_direct_call(monkeypatch):
    """Invoke internal governance without env var and without --yes → exit 1."""
    monkeypatch.delenv("VIBE3_ASYNC_CHILD", raising=False)
    with patch(
        "vibe3.roles.scan_service.dispatch_governance_execution"
    ) as mock_dispatch:
        result = runner.invoke(cli_app, ["internal", "governance", "8", "0"])
        assert result.exit_code == 1
        mock_dispatch.assert_not_called()


# Existing tests: updated to set VIBE3_ASYNC_CHILD via monkeypatch


def test_internal_manager_dispatch(monkeypatch):
    """测试 internal manager 命令参数解析和调用."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(cli_app, ["internal", "manager", "123", "--no-async"])

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["dry_run"] is False
        assert mock_run.call_args.kwargs["show_prompt"] is False
        assert mock_run.call_args.kwargs["fresh_session"] is False
        assert mock_run.call_args.kwargs["spec"].role_name == "manager"


def test_internal_manager_dry_run(monkeypatch):
    """测试 internal manager --dry-run 参数透传."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app, ["internal", "manager", "123", "--no-async", "--dry-run"]
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["dry_run"] is True
        assert mock_run.call_args.kwargs["show_prompt"] is False


def test_internal_manager_show_prompt(monkeypatch):
    """测试 internal manager --show-prompt 参数透传."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "manager", "123", "--no-async", "--dry-run", "--show-prompt"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["dry_run"] is True
        assert mock_run.call_args.kwargs["show_prompt"] is True


def test_internal_manager_branch_override(monkeypatch):
    """测试 internal manager --branch 参数透传 (sync path)."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            [
                "internal",
                "manager",
                "123",
                "--no-async",
                "--dry-run",
                "--branch",
                "task/issue-1905",
            ],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["branch"] == "task/issue-1905"


def test_internal_manager_branch_override_async(monkeypatch):
    """测试 internal manager --branch 参数透传 (async path)."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_async"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "manager", "123", "--branch", "task/issue-1905"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["branch"] == "task/issue-1905"
        assert mock_run.call_args.kwargs["dry_run"] is False


def test_internal_manager_branch_numeric(monkeypatch):
    """测试 --branch 接受 issue number，CLI 层透传原始值由 runner 解析."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "manager", "123", "--no-async", "--branch", "1905"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["branch"] == "1905"


def test_internal_apply_dispatch(monkeypatch):
    """测试 internal apply 命令参数解析和调用."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "apply", "42", "--no-async"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 42
        assert mock_run.call_args.kwargs["dry_run"] is False
        assert mock_run.call_args.kwargs["fresh_session"] is True
        assert mock_run.call_args.kwargs["spec"].role_name == "supervisor"


def test_internal_governance_dispatch_forwards_tick_and_material(monkeypatch):
    """测试 internal governance 会透传 tick 和 material."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
    with patch(
        "vibe3.roles.scan_service.dispatch_governance_execution"
    ) as mock_dispatch:
        result = runner.invoke(
            cli_app,
            ["internal", "governance", "8", "0", "--material", "roadmap-intake"],
        )

        assert result.exit_code == 0
        mock_dispatch.assert_called_once_with(
            tick_count=8,
            execution_count=0,
            material_override="roadmap-intake",
        )


def test_internal_hidden_from_help():
    """测试 internal 命令对用户不可见."""
    result = runner.invoke(cli_app, ["--help"])
    # internal 命令应该出现在帮助信息中,但标注为 hidden
    assert "internal" not in result.stdout or "Internal" in result.stdout


def test_internal_bootstrap_dispatch() -> None:
    """internal bootstrap should call shared bootstrap service."""
    issue_payload = {
        "number": 123,
        "title": "Bootstrap me",
        "state": "OPEN",
        "labels": [{"name": "state/claimed"}],
        "assignees": [],
        "comments": [],
    }

    with patch("vibe3.commands.internal.load_orchestra_config") as load_config:
        load_config.return_value = MagicMock(repo="owner/repo")
        with patch("vibe3.clients.sqlite_client.SQLiteClient"):
            with patch("vibe3.clients.git_client.GitClient"):
                with patch("vibe3.clients.github_client.GitHubClient") as github_cls:
                    with patch(
                        "vibe3.services.orchestra.FlowOrchestratorService"
                    ) as service_cls:
                        with patch(
                            "vibe3.commands.flow_manage.ensure_current_handoff_for_flow"
                        ) as mock_ensure_handoff:
                            github = MagicMock()
                            github.view_issue.return_value = issue_payload
                            github_cls.return_value = github
                            service = MagicMock()
                            service.bootstrap_issue_flow.return_value = {
                                "branch": "dev/issue-123",
                                "worktree_path": "/tmp/dev-issue-123",
                            }
                            service_cls.return_value = service

                            result = runner.invoke(
                                cli_app,
                                [
                                    "internal",
                                    "bootstrap",
                                    "123",
                                    "--branch",
                                    "dev/issue-123",
                                    "--worktree",
                                    "--related",
                                    "456",
                                    "--dependency",
                                    "789",
                                ],
                            )

    assert result.exit_code == 0
    service.bootstrap_issue_flow.assert_called_once()
    call = service.bootstrap_issue_flow.call_args
    issue_info = call.args[0]
    assert issue_info.number == 123
    assert call.kwargs["branch"] == "dev/issue-123"
    assert call.kwargs["ensure_worktree"] is True
    assert call.kwargs["related_issue_numbers"] == (456,)
    assert call.kwargs["dependency_issue_numbers"] == (789,)
    assert call.kwargs["blocked_reason"] is None
    payload = json.loads(result.stdout)
    assert payload["branch"] == "dev/issue-123"
    # Verify handoff helper is called with source="bootstrap"
    mock_ensure_handoff.assert_called_once_with("dev/issue-123", source="bootstrap")


def test_internal_bootstrap_rejects_dependency_and_reason_together() -> None:
    """internal bootstrap should reject blocked reason when dependencies exist."""
    issue_payload = {
        "number": 123,
        "title": "Bootstrap me",
        "state": "OPEN",
        "labels": [{"name": "state/claimed"}],
        "assignees": [],
        "comments": [],
    }

    with patch("vibe3.commands.internal.load_orchestra_config") as load_config:
        load_config.return_value = MagicMock(repo="owner/repo")
        with patch("vibe3.clients.sqlite_client.SQLiteClient"):
            with patch("vibe3.clients.git_client.GitClient"):
                with patch("vibe3.clients.github_client.GitHubClient") as github_cls:
                    with patch(
                        "vibe3.services.orchestra.FlowOrchestratorService"
                    ) as service_cls:
                        github = MagicMock()
                        github.view_issue.return_value = issue_payload
                        github_cls.return_value = github
                        service = MagicMock()
                        service_cls.return_value = service

                        result = runner.invoke(
                            cli_app,
                            [
                                "internal",
                                "bootstrap",
                                "123",
                                "--branch",
                                "dev/issue-123",
                                "--dependency",
                                "789",
                                "--blocked-reason",
                                "manual block",
                            ],
                        )

    assert result.exit_code == 1
    assert "不能同时指定" in result.output
    service.bootstrap_issue_flow.assert_not_called()


# Tests for optional issue parameter with flow resolution


def test_internal_manager_optional_issue_resolves_from_flow(monkeypatch):
    """Test that internal manager resolves issue from current flow."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    # Mock FlowService to return a flow with bound issue
    mock_flow = MagicMock()
    mock_flow.task_issue_number = 999

    with patch("vibe3.services.flow.FlowService") as flow_service_cls:
        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/issue-999"
        flow_service.get_flow_status.return_value = mock_flow
        flow_service_cls.return_value = flow_service

        with patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
        ) as mock_run:
            result = runner.invoke(cli_app, ["internal", "manager", "--no-async"])

            assert result.exit_code == 0
            # Should have called with issue 999 from the mock flow
            assert mock_run.call_args.kwargs["issue_number"] == 999


def test_internal_manager_optional_issue_no_current_branch(monkeypatch):
    """Test error when no issue specified and no current branch detected."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    with patch("vibe3.services.flow.FlowService") as flow_service_cls:
        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = None
        flow_service_cls.return_value = flow_service

        result = runner.invoke(cli_app, ["internal", "manager", "--no-async"])

        assert result.exit_code == 1
        assert "No current branch detected" in result.output


def test_internal_manager_optional_issue_no_flow_found(monkeypatch):
    """Test error when no issue specified and no flow found for branch."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    with patch("vibe3.services.flow.FlowService") as flow_service_cls:
        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/issue-999"
        flow_service.get_flow_status.return_value = None
        flow_service_cls.return_value = flow_service

        result = runner.invoke(cli_app, ["internal", "manager", "--no-async"])

        assert result.exit_code == 1
        assert "No flow found for branch" in result.output


def test_internal_manager_optional_issue_flow_no_bound_issue(monkeypatch):
    """Test error when no issue specified and flow has no bound issue."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    # Mock flow without bound issue
    mock_flow = MagicMock()
    mock_flow.task_issue_number = None

    with patch("vibe3.services.flow.FlowService") as flow_service_cls:
        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/issue-999"
        flow_service.get_flow_status.return_value = mock_flow
        flow_service_cls.return_value = flow_service

        result = runner.invoke(cli_app, ["internal", "manager", "--no-async"])

        assert result.exit_code == 1
        assert "has no bound issue" in result.output


def test_internal_manager_optional_issue_with_branch_override(monkeypatch):
    """Test that --branch parameter works with optional issue resolution."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    # Mock FlowService to return a flow with bound issue
    mock_flow = MagicMock()
    mock_flow.task_issue_number = 777

    with patch("vibe3.services.flow.FlowService") as flow_service_cls:
        flow_service = MagicMock()
        # When --branch is specified, it should be used instead of current branch
        flow_service.get_flow_status.return_value = mock_flow
        flow_service_cls.return_value = flow_service

        with patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
        ) as mock_run:
            result = runner.invoke(
                cli_app,
                ["internal", "manager", "--no-async", "--branch", "dev/issue-777"],
            )

            assert result.exit_code == 0
            # Should have called with issue 777 from the mock flow
            assert mock_run.call_args.kwargs["issue_number"] == 777
            assert mock_run.call_args.kwargs["branch"] == "dev/issue-777"


def test_internal_manager_show_prompt_forces_sync_path(monkeypatch):
    """Test that --show-prompt forces sync execution (no_async=True)."""
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_sync:
        with patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_async"
        ) as mock_async:
            result = runner.invoke(
                cli_app,
                [
                    "internal",
                    "manager",
                    "123",
                    "--dry-run",
                    "--show-prompt",
                ],
            )

            assert result.exit_code == 0
            # Should have called sync path, NOT async
            mock_sync.assert_called_once()
            mock_async.assert_not_called()
            # Verify show_prompt was passed
            assert mock_sync.call_args.kwargs["show_prompt"] is True


class TestManagerDryRunResultDisplay:
    """Manager --dry-run must use sync execution and display via
    _handle_codeagent_result, consistent with plan/run/review commands."""

    @patch("vibe3.commands.common._handle_codeagent_result")
    def test_manager_dry_run_uses_handle_codeagent_result(self, mock_handle):
        """Manager --dry-run passes CodeagentResult to _handle_codeagent_result."""
        from vibe3.agents import CodeagentResult

        fake_result = CodeagentResult(
            success=True,
            backend="anthropic",
            model="claude-opus-4-8",
            issue_number=123,
        )

        with patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync",
            return_value=fake_result,
        ) as mock_sync:
            with patch(
                "vibe3.execution.issue_role_sync_runner.run_issue_role_async"
            ) as mock_async:
                result = runner.invoke(
                    cli_app,
                    ["internal", "manager", "123", "--dry-run", "--no-async", "--yes"],
                )

        assert result.exit_code == 0
        mock_sync.assert_called_once()
        mock_async.assert_not_called()
        mock_handle.assert_called_once()
        call_args = mock_handle.call_args
        result_arg = call_args[0][0]
        assert result_arg.success is True
        assert result_arg.backend == "anthropic"
        assert result_arg.model == "claude-opus-4-8"
        assert call_args[0][1] == "Manager"

    @patch("vibe3.commands.common._handle_codeagent_result")
    def test_manager_dry_run_forces_sync_execution(self, mock_handle):
        """Manager --dry-run (without --no-async) forces sync execution."""
        from vibe3.agents import CodeagentResult

        fake_result = CodeagentResult(
            success=True,
            backend="openai",
            model="gpt-5",
            issue_number=123,
        )

        with patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync",
            return_value=fake_result,
        ) as mock_sync:
            with patch(
                "vibe3.execution.issue_role_sync_runner.run_issue_role_async"
            ) as mock_async:
                result = runner.invoke(
                    cli_app,
                    ["internal", "manager", "123", "--dry-run", "--yes"],
                )

        assert result.exit_code == 0
        # --dry-run forces sync execution, not async
        mock_sync.assert_called_once()
        mock_async.assert_not_called()
        mock_handle.assert_called_once()
        call_args = mock_handle.call_args
        result_arg = call_args[0][0]
        assert result_arg.success is True
        assert result_arg.backend == "openai"
        assert result_arg.model == "gpt-5"
        assert call_args[0][1] == "Manager"
