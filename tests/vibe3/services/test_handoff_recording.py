"""Tests for handoff recording operations."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.services.handoff_service import HandoffService


@pytest.fixture
def mock_store():
    """Create a mock SQLiteClient."""
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = MagicMock(spec=GitClient)
    client.get_current_branch.return_value = "feature/test-branch"
    return client


@pytest.fixture
def handoff_service(mock_store, mock_git_client):
    """Create a HandoffService instance with mocked dependencies."""
    return HandoffService(store=mock_store, git_client=mock_git_client)


class TestRecordPlan:
    """Tests for record_plan method."""

    def test_record_plan_success(self, handoff_service, mock_store, mock_git_client):
        """Test successful plan recording."""
        mock_git_client.get_current_branch.return_value = "feature/test-branch"

        handoff_service.record_plan(
            plan_ref="docs/plans/feature-x.md",
            next_step="Implement feature",
            blocked_by=None,
            actor="claude/sonnet-4.6",
        )

        mock_store.update_flow_state.assert_called_once_with(
            "feature/test-branch",
            plan_ref="docs/plans/feature-x.md",
            planner_actor="claude/sonnet-4.6",
            latest_actor="claude/sonnet-4.6",
            next_step="Implement feature",
            blocked_by=None,
        )
        mock_store.add_event.assert_called_once()

    def test_record_plan_with_blocker(
        self, handoff_service, mock_store, mock_git_client
    ):
        """Test plan recording with blocker."""
        mock_git_client.get_current_branch.return_value = "feature/test-branch"

        handoff_service.record_plan(
            plan_ref="docs/plans/feature-y.md",
            next_step=None,
            blocked_by="Waiting for API access",
            actor="claude/sonnet-4.6",
        )

        mock_store.update_flow_state.assert_called_once()


class TestRecordReport:
    """Tests for record_report method."""

    def test_record_report_success(self, handoff_service, mock_store, mock_git_client):
        """Test successful report recording."""
        mock_git_client.get_current_branch.return_value = "feature/test-branch"

        handoff_service.record_report(
            report_ref="docs/reports/review-42.md",
            next_step="Address review comments",
            blocked_by=None,
            actor="codex/gpt-5.4",
        )

        mock_store.update_flow_state.assert_called_once_with(
            "feature/test-branch",
            report_ref="docs/reports/review-42.md",
            reviewer_actor="codex/gpt-5.4",
            latest_actor="codex/gpt-5.4",
            next_step="Address review comments",
            blocked_by=None,
        )
        mock_store.add_event.assert_called_once()


class TestRecordAudit:
    """Tests for record_audit method."""

    def test_record_audit_success(self, handoff_service, mock_store, mock_git_client):
        """Test successful audit recording."""
        mock_git_client.get_current_branch.return_value = "feature/test-branch"

        handoff_service.record_audit(
            audit_ref="docs/audits/security-check.md",
            next_step="Fix security issues",
            blocked_by=None,
            actor="copilot/gpt-4",
        )

        mock_store.update_flow_state.assert_called_once_with(
            "feature/test-branch",
            audit_ref="docs/audits/security-check.md",
            reviewer_actor="copilot/gpt-4",
            latest_actor="copilot/gpt-4",
            next_step="Fix security issues",
            blocked_by=None,
        )
        mock_store.add_event.assert_called_once()