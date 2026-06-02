"""Tests for branch_arg resolver wrapper."""

from unittest.mock import Mock, patch

from vibe3.services.branch_arg import resolve_branch_arg


class TestResolveBranchArg:
    """测试 resolve_branch_arg 薄包装行为"""

    def test_none_returns_current_branch(self):
        """测试：None 输入返回当前分支"""
        with patch("vibe3.services.branch_arg.FlowService") as mock_fs_cls:
            mock_flow_service = Mock()
            mock_fs_cls.return_value = mock_flow_service
            mock_flow_service.get_current_branch.return_value = "dev/issue-123"

            result = resolve_branch_arg(None)
            assert result == "dev/issue-123"

    def test_issue_number_returns_canonical_branch(self):
        """测试：纯数字输入返回 canonical branch（无 flow 时）"""
        with patch("vibe3.services.branch_arg.FlowService") as mock_fs_cls:
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
        with patch("vibe3.services.branch_arg.FlowService") as mock_fs_cls:
            mock_flow_service = Mock()
            mock_fs_cls.return_value = mock_flow_service

            mock_store = Mock()
            mock_flow_service.store = mock_store
            mock_store.get_flows_by_issue.return_value = []
            mock_store.get_flow_state.return_value = None

            result = resolve_branch_arg("dev/issue-789")
            assert result == "dev/issue-789"
