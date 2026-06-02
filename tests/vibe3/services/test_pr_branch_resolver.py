"""Tests for PR to Branch resolver."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from vibe3.exceptions import UserError
from vibe3.services.pr_branch_resolver import (
    resolve_branch_from_pr,
    resolve_command_branch,
)


class TestResolveBranchFromPr:
    """测试 PR → Branch 解析"""

    def test_resolve_success(self):
        """测试正常解析"""
        mock_pr = Mock()
        mock_pr.head_branch = "dev/issue-476"

        mock_client = Mock()
        mock_client.get_pr.return_value = mock_pr

        result = resolve_branch_from_pr(1183, github_client=mock_client)
        assert result == "dev/issue-476"
        mock_client.get_pr.assert_called_once_with(1183)

    def test_pr_not_found(self):
        """测试 PR 不存在"""
        mock_client = Mock()
        mock_client.get_pr.return_value = None

        with pytest.raises(UserError) as exc_info:
            resolve_branch_from_pr(9999, github_client=mock_client)

        assert "PR #9999 不存在" in str(exc_info.value)

    def test_network_error(self):
        """测试网络错误"""
        mock_client = Mock()
        mock_client.get_pr.side_effect = Exception("Network timeout")

        with pytest.raises(UserError) as exc_info:
            resolve_branch_from_pr(1183, github_client=mock_client)

        assert "无法获取 PR #1183" in str(exc_info.value)
        assert "Network timeout" in str(exc_info.value)

    def test_pr_missing_branch(self):
        """测试 PR 缺少分支信息"""
        mock_pr = Mock()
        mock_pr.head_branch = None

        mock_client = Mock()
        mock_client.get_pr.return_value = mock_pr

        with pytest.raises(UserError) as exc_info:
            resolve_branch_from_pr(1183, github_client=mock_client)

        assert "无法从 PR #1183 获取分支名" in str(exc_info.value)

    def test_gh_not_installed_which_check(self):
        """Test gh CLI not found by shutil.which raises UserError."""
        mock_client = Mock()

        with patch("shutil.which", return_value=None):
            with pytest.raises(UserError) as exc_info:
                resolve_branch_from_pr(1183, github_client=mock_client)

        assert "gh CLI 未安装" in str(exc_info.value)
        mock_client.get_pr.assert_not_called()

    def test_gh_not_installed_file_not_found(self):
        """Test FileNotFoundError from get_pr raises descriptive UserError."""
        mock_client = Mock()
        mock_client.get_pr.side_effect = FileNotFoundError("gh not found")

        with patch("shutil.which", return_value="/usr/local/bin/gh"):
            with pytest.raises(UserError) as exc_info:
                resolve_branch_from_pr(1183, github_client=mock_client)

        assert "gh CLI 不可用" in str(exc_info.value)


class TestResolveCommandBranch:
    """测试统一命令分支解析"""

    def test_priority_explicit_branch(self):
        """测试优先级：--branch 最高"""
        mock_flow_service = Mock()
        mock_flow_service.get_current_branch.return_value = "main"

        # Mock resolve_issue_branch_input
        with patch(
            "vibe3.services.pr_branch_resolver.resolve_issue_branch_input"
        ) as mock_resolve:
            mock_resolve.return_value = "dev/issue-476"

            result = resolve_command_branch(
                branch_opt="dev/issue-476",
                flow_service=mock_flow_service,
            )

            # 应该调用 resolve_issue_branch_input
            mock_resolve.assert_called_once_with(
                "dev/issue-476", mock_flow_service, allow_no_flow=False
            )
            # 返回解析后的分支
            assert result == "dev/issue-476"

    def test_priority_pr_option(self):
        """测试优先级：--pr 次之"""
        mock_pr = Mock()
        mock_pr.head_branch = "dev/issue-476"

        mock_client = Mock()
        mock_client.get_pr.return_value = mock_pr

        mock_flow_service = Mock()

        result = resolve_command_branch(
            pr_opt=1183,
            flow_service=mock_flow_service,
            github_client=mock_client,
        )

        assert result == "dev/issue-476"
        mock_client.get_pr.assert_called_once_with(1183)

    def test_priority_position_arg(self):
        """测试优先级：位置参数"""
        mock_flow_service = Mock()

        with patch(
            "vibe3.services.pr_branch_resolver.resolve_issue_branch_input"
        ) as mock_resolve:
            mock_resolve.return_value = "task/issue-999"

            result = resolve_command_branch(
                position_arg="999",
                flow_service=mock_flow_service,
            )

            mock_resolve.assert_called_once_with(
                "999", mock_flow_service, allow_no_flow=False
            )
            assert result == "task/issue-999"

    def test_fallback_current_branch(self):
        """测试回退：当前分支"""
        mock_flow_service = Mock()
        mock_flow_service.get_current_branch.return_value = "main"

        result = resolve_command_branch(flow_service=mock_flow_service)

        assert result == "main"
        mock_flow_service.get_current_branch.assert_called_once()

    def test_conflict_detection(self):
        """测试参数冲突检测"""
        mock_flow_service = Mock()

        # typer.Exit 继承自 click.exceptions.Exit
        from click.exceptions import Exit

        with pytest.raises(Exit) as exc_info:
            resolve_command_branch(
                branch_opt="dev/issue-476",
                pr_opt=1183,
                flow_service=mock_flow_service,
            )

        assert exc_info.value.exit_code == 1

    def test_pr_resolution_error(self):
        """测试 PR 解析错误传播"""
        mock_client = Mock()
        mock_client.get_pr.return_value = None

        mock_flow_service = Mock()

        with pytest.raises(UserError) as exc_info:
            resolve_command_branch(
                pr_opt=9999,
                flow_service=mock_flow_service,
                github_client=mock_client,
            )

        assert "PR #9999 不存在" in str(exc_info.value)


class TestResolveCommandBranchCanonicalFallback:
    """测试 canonical_fallback 参数"""

    def test_canonical_fallback_with_issue_number_no_flow(self):
        """测试：纯数字输入无 flow 时返回 canonical branch"""
        from unittest.mock import Mock

        from vibe3.services.pr_branch_resolver import resolve_command_branch

        mock_store = Mock()
        mock_store.get_flows_by_issue.return_value = []  # No flows
        mock_store.get_flow_state.return_value = None  # No candidates

        mock_flow_service = Mock()
        mock_flow_service.store = mock_store
        mock_flow_service.get_current_branch.return_value = "main"

        result = resolve_command_branch(
            branch_opt="1234",
            flow_service=mock_flow_service,
            canonical_fallback=True,
        )

        # Should return canonical branch, not raise UserError
        assert result == "task/issue-1234"

    def test_canonical_fallback_false_raises_error_no_flow(self):
        """测试：canonical_fallback=False 时仍抛出 UserError"""
        from unittest.mock import Mock

        from vibe3.exceptions import UserError
        from vibe3.services.pr_branch_resolver import resolve_command_branch

        mock_store = Mock()
        mock_store.get_flows_by_issue.return_value = []
        mock_store.get_flow_state.return_value = None

        mock_flow_service = Mock()
        mock_flow_service.store = mock_store

        with pytest.raises(UserError) as exc_info:
            resolve_command_branch(
                branch_opt="1234",
                flow_service=mock_flow_service,
                canonical_fallback=False,
            )

        assert "No flow found for issue #1234" in str(exc_info.value)

    def test_canonical_fallback_ignored_for_branch_name(self):
        """测试：非数字输入时 canonical_fallback 无效"""
        from unittest.mock import Mock

        from vibe3.services.pr_branch_resolver import resolve_command_branch

        mock_flow_service = Mock()
        mock_flow_service.get_current_branch.return_value = "main"

        result = resolve_command_branch(
            branch_opt="dev/issue-999",
            flow_service=mock_flow_service,
            canonical_fallback=True,
        )

        # Should return as-is (branch name)
        assert result == "dev/issue-999"


class TestCommandIntegration:
    """测试命令集成"""

    def test_flow_show_with_pr(self):
        """测试 flow show --pr 集成"""
        from vibe3.cli import app

        runner = CliRunner()

        # Mock GitHub client
        with patch("vibe3.clients.github_client.GitHubClient") as mock_github_class:
            mock_client = Mock()
            mock_pr = Mock()
            mock_pr.head_branch = "dev/issue-476"
            mock_client.get_pr.return_value = mock_pr
            mock_github_class.return_value = mock_client

            # Mock FlowService
            with patch("vibe3.services.flow_service.FlowService") as mock_service_class:
                mock_service = Mock()
                mock_service.get_current_branch.return_value = "main"
                mock_service_class.return_value = mock_service

                # 运行命令
                result = runner.invoke(app, ["flow", "show", "--pr", "1183"])

                # 验证参数解析成功（不应该出现 "No such option" 错误）
                # exit_code 2 表示 Click 参数解析失败
                assert result.exit_code != 2
                # 输出不应该包含选项错误
                assert "No such option: --pr" not in result.output

    def test_handoff_status_with_pr(self):
        """测试 handoff status --pr 集成"""
        from vibe3.cli import app

        runner = CliRunner()

        # 类似上面的测试，验证参数解析
        result = runner.invoke(app, ["handoff", "status", "--pr", "1183"])
        # 验证参数解析成功
        assert result.exit_code != 2
        assert "No such option: --pr" not in result.output

    def test_task_show_with_pr(self):
        """测试 task show --pr 集成"""
        from vibe3.cli import app

        runner = CliRunner()

        # 类似上面的测试，验证参数解析
        result = runner.invoke(app, ["task", "show", "--pr", "1183"])
        # 验证参数解析成功
        assert result.exit_code != 2
        assert "No such option: --pr" not in result.output
