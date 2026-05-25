"""Tests for issue_branch_resolver conflict detection."""

from unittest.mock import Mock, patch

import pytest

from vibe3.exceptions import UserError
from vibe3.services.issue_branch_resolver import (
    _format_flow_details,
    resolve_issue_branch_input,
)


@pytest.fixture
def mock_flow_service() -> Mock:
    """Create mock FlowService with store."""
    service = Mock()
    service.store = Mock()
    service.get_flow_state = Mock()
    return service


@pytest.fixture
def mock_store(mock_flow_service: Mock) -> Mock:
    """Get store from mock_flow_service."""
    return mock_flow_service.store


def test_single_non_aborted_flow_auto_select(mock_flow_service: Mock, mock_store: Mock):
    """Test auto-selection when only one non-aborted flow exists."""
    # Arrange: Single active flow with issue binding
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        }
    ]

    # Act: Resolve issue number
    result = resolve_issue_branch_input("976", mock_flow_service)

    # Assert: Returns correct branch
    assert result == "dev/issue-976"
    mock_store.get_flows_by_issue.assert_called_once_with(976, role="task")


def test_multiple_non_aborted_one_active_auto_select(
    mock_flow_service: Mock, mock_store: Mock
):
    """Test auto-selection when one aborted and one active flow exist."""
    # Arrange: One aborted, one active
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "task/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        },
    ]

    # Act: Resolve issue number
    result = resolve_issue_branch_input("976", mock_flow_service)

    # Assert: Returns active branch
    assert result == "dev/issue-976"
    mock_store.get_flows_by_issue.assert_called_once_with(976, role="task")


def test_multiple_active_flows_conflict_error(
    mock_flow_service: Mock, mock_store: Mock
):
    """Test error when multiple active flows exist."""
    # Arrange: Multiple active flows
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        },
        {
            "branch": "task/issue-976",
            "flow_status": "active",
            "pr_ref": None,
        },
    ]

    # Act & Assert: Should raise UserError with helpful message
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "Multiple active flows detected" in error_message
    assert "vibe3 flow abort" in error_message


def test_all_aborted_flows_error(mock_flow_service: Mock, mock_store: Mock):
    """Test error when all flows are aborted."""
    # Arrange: All flows aborted
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "task/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
        {
            "branch": "dev/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
    ]

    # Act & Assert: Should raise UserError with restore hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "All flows for issue" in error_message
    assert "aborted" in error_message
    assert "vibe3 flow restore" in error_message


def test_no_binding_with_candidates_error(mock_flow_service: Mock, mock_store: Mock):
    """Test error when no binding but unbound candidates exist."""
    # Arrange: No flows by issue, but unbound candidate exists
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = {
        "branch": "dev/issue-976",
        "flow_status": "active",
        "pr_ref": None,
    }

    # Act & Assert: Should raise UserError with bind hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "without task binding" in error_message
    assert "vibe3 flow bind" in error_message


def test_no_flows_at_all_error(mock_flow_service: Mock, mock_store: Mock):
    """Test error when no flows exist at all."""
    # Arrange: No flows anywhere
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = None

    # Act & Assert: Should raise UserError with vibe-new hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "No flow found" in error_message
    assert "/vibe-new" in error_message


def test_format_flow_details_with_pr():
    """Test _format_flow_details formats flow with PR correctly."""
    flow = {
        "branch": "dev/issue-976",
        "flow_status": "active",
        "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
    }

    result = _format_flow_details(flow)

    assert result == "dev/issue-976 (status: active, pr: #990)"


def test_format_flow_details_without_pr():
    """Test _format_flow_details formats flow without PR correctly."""
    flow = {
        "branch": "task/issue-976",
        "flow_status": "aborted",
        "pr_ref": None,
    }

    result = _format_flow_details(flow)

    assert result == "task/issue-976 (status: aborted, pr: none)"


class TestResolveIssueBranchInputAllowNoFlow:
    """测试 allow_no_flow 参数"""

    def test_allow_no_flow_returns_none_for_no_flow(self):
        """测试当没有 flow 时，allow_no_flow=True 返回 None 而不是抛出异常"""
        mock_store = Mock()
        mock_store.get_flows_by_issue.return_value = []  # No flows
        mock_store.get_flow_state.return_value = None  # No candidates

        mock_flow_service = Mock()
        mock_flow_service.store = mock_store

        result = resolve_issue_branch_input(
            "1357",
            mock_flow_service,
            allow_no_flow=True,
        )

        assert result is None
        mock_store.get_flows_by_issue.assert_called_once_with(1357, role="task")

    def test_allow_no_flow_false_raises_user_error(self):
        """测试当没有 flow 时，allow_no_flow=False 抛出 UserError（默认行为）"""
        mock_store = Mock()
        mock_store.get_flows_by_issue.return_value = []
        mock_store.get_flow_state.return_value = None

        mock_flow_service = Mock()
        mock_flow_service.store = mock_store

        with pytest.raises(UserError) as exc_info:
            resolve_issue_branch_input(
                "1357",
                mock_flow_service,
                allow_no_flow=False,
            )

        assert "No flow found for issue #1357" in str(exc_info.value)

    def test_allow_no_flow_returns_branch_when_flow_exists(self):
        """测试当 flow 存在时，allow_no_flow 参数不影响正常解析"""
        mock_store = Mock()
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "dev/issue-1357", "flow_status": "active", "pr_ref": None}
        ]

        mock_flow_service = Mock()
        mock_flow_service.store = mock_store

        result = resolve_issue_branch_input(
            "1357",
            mock_flow_service,
            allow_no_flow=True,
        )

        assert result == "dev/issue-1357"


class TestResolveIssueBranchInputPrDetection:
    """测试位置参数传入 PR 号时的检测和提示"""

    def test_position_arg_pr_number_detected_allow_no_flow_true(self):
        """测试 allow_no_flow=True 时，传入 PR 号抛出 UserError 并提示使用 --pr"""
        mock_store = Mock()
        mock_store.get_flows_by_issue.return_value = []
        mock_store.get_flow_state.return_value = None

        mock_flow_service = Mock()
        mock_flow_service.store = mock_store

        # Mock subprocess to return PR data
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"headRefName": "dev/issue-1414", "number": 1422}'

        with patch(
            "vibe3.services.issue_branch_resolver.subprocess.run",
            return_value=mock_result,
        ):
            with pytest.raises(UserError) as exc_info:
                resolve_issue_branch_input(
                    "1422", mock_flow_service, allow_no_flow=True
                )

        error_msg = str(exc_info.value)
        assert "Pull Request" in error_msg or "PR" in error_msg
        assert "--pr" in error_msg

    def test_position_arg_real_issue_no_pr_hint(self):
        """测试传入真实 issue 号（不是 PR），不提示 PR"""
        mock_store = Mock()
        mock_store.get_flows_by_issue.return_value = []
        mock_store.get_flow_state.return_value = None

        mock_flow_service = Mock()
        mock_flow_service.store = mock_store

        # Mock subprocess to return not-a-PR (headRefName is None or fails)
        mock_result = Mock()
        mock_result.returncode = 1  # gh pr view fails, not a PR
        mock_result.stdout = ""

        with patch(
            "vibe3.services.issue_branch_resolver.subprocess.run",
            return_value=mock_result,
        ):
            result = resolve_issue_branch_input(
                "1419", mock_flow_service, allow_no_flow=True
            )

        # Should return None (no flow, allow_no_flow=True)
        assert result is None

    def test_position_arg_branch_name_not_detected_as_pr(self):
        """测试传入 branch 名（非数字），不触发 PR 检测"""
        mock_flow_service = Mock()

        result = resolve_issue_branch_input(
            "dev/issue-1414", mock_flow_service, allow_no_flow=True
        )

        # Non-digit input returned as-is, no PR check
        assert result == "dev/issue-1414"
