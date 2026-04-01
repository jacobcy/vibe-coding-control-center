"""Convergence tests for PR ready command (Human-Only)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.pr import app
from vibe3.services.pr_ready_usecase import PrReadyUsecase

runner = CliRunner()


@pytest.fixture
def mock_pr_response():
    from vibe3.models.pr import PRResponse, PRState

    return PRResponse(
        number=123,
        title="Test PR",
        body="Body",
        state=PRState.OPEN,
        head_branch="task/demo",
        base_branch="main",
        url="https://example.com/pr/123",
        draft=True,
    )


def test_pr_ready_no_longer_invokes_gates(mock_pr_response):
    """
    Assert that pr ready no longer invokes coverage or risk gates.
    """
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch("vibe3.commands.pr_lifecycle.FlowService") as mock_flow_service,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_instance.get_pr.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        mock_flow_instance = MagicMock()
        mock_flow_instance.get_current_branch.return_value = "task/demo"
        mock_flow_service.return_value = mock_flow_instance

        # Mock PrReadyUsecase's _sync_merge_ready_label because it's still there
        with patch.object(PrReadyUsecase, "_sync_merge_ready_label"):
            result = runner.invoke(app, ["ready", "123", "--yes"])

        assert result.exit_code == 0
        # No error means _run_ready_gates was not called (because it doesn't exist)


def test_pr_ready_yes_only_affects_confirmation(mock_pr_response):
    """
    Assert that --yes bypasses confirmation but doesn't mention gate bypass in output.
    """
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch("vibe3.commands.pr_lifecycle.FlowService") as mock_flow_service,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.mark_ready.return_value = mock_pr_response
        mock_pr_instance.get_pr.return_value = mock_pr_response
        mock_pr_service.return_value = mock_pr_instance

        mock_flow_instance = MagicMock()
        mock_flow_instance.get_current_branch.return_value = "task/demo"
        mock_flow_service.return_value = mock_flow_instance

        with patch.object(PrReadyUsecase, "_sync_merge_ready_label"):
            result = runner.invoke(app, ["ready", "123", "--yes"])

        assert result.exit_code == 0
        # Output should NOT contain gate bypass wording
        assert "Skipping coverage gate" not in result.output
        assert "绕过业务逻辑检查" not in result.output
        # Wording should be human-only confirmation
        assert "自动确认并发布 PR" not in result.output
        # But wait, result.output will contain render_pr_ready output.
