"""Tests for branch_arg resolver wrapper."""

from unittest.mock import Mock, patch

from vibe3.services.shared.branches import resolve_branch_and_issue, resolve_branch_arg


class TestResolveBranchArg:
    """测试 resolve_branch_arg 薄包装行为"""

    def test_none_returns_current_branch(self):
        """测试：None 输入返回当前分支"""
        from unittest.mock import MagicMock

        mock_flow_service = Mock()
        mock_git_client = MagicMock()
        mock_git_client.get_current_branch.return_value = "dev/issue-123"

        with (
            patch("vibe3.services.FlowService") as mock_fs_cls,
            patch("vibe3.clients.GitClient") as mock_git_cls,
        ):
            mock_fs_cls.return_value = mock_flow_service
            mock_git_cls.return_value = mock_git_client

            result = resolve_branch_arg(None)
            assert result == "dev/issue-123"

    def test_issue_number_returns_canonical_branch(self):
        """测试：纯数字输入返回 canonical branch（无 flow 时）"""
        with patch("vibe3.services.FlowService") as mock_fs_cls:
            mock_flow_service = Mock()
            mock_fs_cls.return_value = mock_flow_service

            mock_store = Mock()
            mock_flow_service.store = mock_store
            mock_store.get_flows_by_issue.return_value = []
            mock_store.get_flow_state.return_value = None

            result = resolve_branch_arg("456")
            assert result == "task/issue-456"

    def test_branch_name_returns_as_is(self):
        """测试：分支名输入返回原值"""
        with patch("vibe3.services.FlowService") as mock_fs_cls:
            mock_flow_service = Mock()
            mock_fs_cls.return_value = mock_flow_service

            mock_store = Mock()
            mock_flow_service.store = mock_store
            mock_store.get_flows_by_issue.return_value = []
            mock_store.get_flow_state.return_value = None

            result = resolve_branch_arg("dev/issue-789")
            assert result == "dev/issue-789"


class TestResolveBranchAndIssue:
    """测试 resolve_branch_and_issue 组合解析行为"""

    def test_none_returns_current_branch_with_issue(self):
        """测试：None 输入返回当前分支和正确的 issue number"""
        with (
            patch("vibe3.services.resolve_branch_arg") as mock_resolve,
            patch(
                "vibe3.config.convention_resolver.get_convention"
            ) as mock_get_convention,
        ):
            mock_resolve.return_value = "task/issue-123"

            mock_branch_convention = Mock()
            mock_branch_convention.parse_issue_number.return_value = 123
            mock_get_convention.return_value.branch = mock_branch_convention

            result = resolve_branch_and_issue(None)
            assert result == ("task/issue-123", 123)
            mock_resolve.assert_called_once_with(None, flow_service=None)

    def test_digit_arg_returns_canonical_with_issue(self):
        """测试：纯数字输入返回 canonical branch 和 issue number"""
        with (
            patch("vibe3.services.resolve_branch_arg") as mock_resolve,
            patch(
                "vibe3.config.convention_resolver.get_convention"
            ) as mock_get_convention,
        ):
            mock_resolve.return_value = "task/issue-123"

            mock_branch_convention = Mock()
            mock_branch_convention.parse_issue_number.return_value = 123
            mock_get_convention.return_value.branch = mock_branch_convention

            result = resolve_branch_and_issue("123")
            assert result == ("task/issue-123", 123)
            mock_resolve.assert_called_once_with("123", flow_service=None)

    def test_branch_name_with_issue(self):
        """测试：分支名输入返回原值和解析出的 issue number"""
        with (
            patch("vibe3.services.resolve_branch_arg") as mock_resolve,
            patch(
                "vibe3.config.convention_resolver.get_convention"
            ) as mock_get_convention,
        ):
            mock_resolve.return_value = "task/issue-456"

            mock_branch_convention = Mock()
            mock_branch_convention.parse_issue_number.return_value = 456
            mock_get_convention.return_value.branch = mock_branch_convention

            result = resolve_branch_and_issue("task/issue-456")
            assert result == ("task/issue-456", 456)
            mock_resolve.assert_called_once_with("task/issue-456", flow_service=None)

    def test_invalid_name_no_issue(self):
        """测试：无效分支名返回原值和 None issue number"""
        with (
            patch("vibe3.services.resolve_branch_arg") as mock_resolve,
            patch(
                "vibe3.config.convention_resolver.get_convention"
            ) as mock_get_convention,
        ):
            mock_resolve.return_value = "invalid-name"

            mock_branch_convention = Mock()
            mock_branch_convention.parse_issue_number.return_value = None
            mock_get_convention.return_value.branch = mock_branch_convention

            result = resolve_branch_and_issue("invalid-name")
            assert result == ("invalid-name", None)
            mock_resolve.assert_called_once_with("invalid-name", flow_service=None)

    def test_return_type_is_tuple(self):
        """测试：返回值类型为 tuple，且元素类型正确"""
        with (
            patch("vibe3.services.resolve_branch_arg") as mock_resolve,
            patch(
                "vibe3.config.convention_resolver.get_convention"
            ) as mock_get_convention,
        ):
            mock_resolve.return_value = "task/issue-789"

            mock_branch_convention = Mock()
            mock_branch_convention.parse_issue_number.return_value = 789
            mock_get_convention.return_value.branch = mock_branch_convention

            result = resolve_branch_and_issue("789")
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], str)
            assert isinstance(result[1], int)
            assert result == ("task/issue-789", 789)
