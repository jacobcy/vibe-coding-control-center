"""Tests for HandoffService."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.services.handoff_service import HandoffService


@pytest.fixture
def temp_git_dir():
    """Create a temporary git directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        git_dir = Path(tmpdir) / ".git"
        git_dir.mkdir()
        yield git_dir


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
            plan_ref="docs/plans/test-plan.md",
            next_step=None,
            blocked_by=None,
            actor="claude/sonnet-4.6",
        )

        # Verify update_flow_state was called
        mock_store.update_flow_state.assert_called_once()
        call_args = mock_store.update_flow_state.call_args
        assert call_args[0][0] == "feature/test-branch"
        assert call_args[1]["plan_ref"] == "docs/plans/test-plan.md"
        assert call_args[1]["planner_actor"] == "claude/sonnet-4.6"
        assert call_args[1]["latest_actor"] == "claude/sonnet-4.6"

        # Verify add_event was called
        mock_store.add_event.assert_called_once()
        event_args = mock_store.add_event.call_args
        assert event_args[0][0] == "feature/test-branch"
        assert event_args[0][1] == "handoff_plan"
        assert event_args[0][2] == "claude/sonnet-4.6"

    def test_record_with_next_step(self, handoff_service, mock_store):
        """Test plan recording with next step."""
        handoff_service.record_plan(
            plan_ref="docs/plans/test-plan.md",
            next_step="Start implementation",
            blocked_by=None,
            actor="claude/sonnet-4.6",
        )

        call_args = mock_store.update_flow_state.call_args
        assert call_args[1]["next_step"] == "Start implementation"

    def test_record_with_blocked_by(self, handoff_service, mock_store):
        """Test plan recording with blocker."""
        handoff_service.record_plan(
            plan_ref="docs/plans/test-plan.md",
            next_step=None,
            blocked_by="Waiting for API key",
            actor="claude/sonnet-4.6",
        )

        call_args = mock_store.update_flow_state.call_args
        assert call_args[1]["blocked_by"] == "Waiting for API key"

    def test_event_recorded(self, handoff_service, mock_store):
        """Test that event is recorded correctly."""
        handoff_service.record_plan(
            plan_ref="docs/plans/test-plan.md",
            next_step=None,
            blocked_by=None,
            actor="claude/sonnet-4.6",
        )

        mock_store.add_event.assert_called_once_with(
            "feature/test-branch",
            "handoff_plan",
            "claude/sonnet-4.6",
            "Plan recorded: docs/plans/test-plan.md",
        )


class TestRecordReport:
    """Tests for record_report method."""

    def test_record_report_success(self, handoff_service, mock_store):
        """Test successful report recording."""
        handoff_service.record_report(
            report_ref="docs/reports/test-report.md",
            next_step=None,
            blocked_by=None,
            actor="claude/sonnet-4.6",
        )

        mock_store.update_flow_state.assert_called_once()
        call_args = mock_store.update_flow_state.call_args
        assert call_args[1]["report_ref"] == "docs/reports/test-report.md"
        assert call_args[1]["reviewer_actor"] == "claude/sonnet-4.6"

        mock_store.add_event.assert_called_once()

    def test_record_with_next_step(self, handoff_service, mock_store):
        """Test report recording with next step."""
        handoff_service.record_report(
            report_ref="docs/reports/test-report.md",
            next_step="Address feedback",
            blocked_by=None,
            actor="claude/sonnet-4.6",
        )

        call_args = mock_store.update_flow_state.call_args
        assert call_args[1]["next_step"] == "Address feedback"


class TestRecordAudit:
    """Tests for record_audit method."""

    def test_record_audit_success(self, handoff_service, mock_store):
        """Test successful audit recording."""
        handoff_service.record_audit(
            audit_ref="docs/audits/test-audit.md",
            next_step=None,
            blocked_by=None,
            actor="claude/sonnet-4.6",
        )

        mock_store.update_flow_state.assert_called_once()
        call_args = mock_store.update_flow_state.call_args
        assert call_args[1]["audit_ref"] == "docs/audits/test-audit.md"
        assert call_args[1]["reviewer_actor"] == "claude/sonnet-4.6"

        mock_store.add_event.assert_called_once()


class TestEnsureCurrentHandoff:
    """Tests for ensure_current_handoff method."""

    @patch("os.popen")
    def test_ensure_current_handoff_creates_template(
        self, mock_popen, handoff_service, temp_git_dir
    ):
        """Test that ensure_current_handoff creates template if not exists."""
        # Mock git directory
        mock_popen.return_value.read.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()

        assert handoff_path.exists()
        assert handoff_path.name == "current.md"
        content = handoff_path.read_text()
        assert "# Handoff: feature/test-branch" in content
        assert "lightweight handoff file" in content

    @patch("os.popen")
    def test_ensure_current_handoff_existing_file(
        self, mock_popen, handoff_service, temp_git_dir
    ):
        """Test that existing file is not overwritten."""
        mock_popen.return_value.read.return_value = str(temp_git_dir)

        # Create file first
        handoff_path = handoff_service.ensure_current_handoff()
        original_content = handoff_path.read_text()

        # Call again
        handoff_path2 = handoff_service.ensure_current_handoff()
        assert handoff_path == handoff_path2
        assert handoff_path.read_text() == original_content


class TestReadCurrentHandoff:
    """Tests for read_current_handoff method."""

    @patch("os.popen")
    def test_read_current_handoff(self, mock_popen, handoff_service, temp_git_dir):
        """Test reading current handoff file."""
        mock_popen.return_value.read.return_value = str(temp_git_dir)

        # Create file
        handoff_service.ensure_current_handoff()

        # Read it
        content = handoff_service.read_current_handoff()
        assert "# Handoff: feature/test-branch" in content

    def test_read_current_handoff_not_found(self, handoff_service):
        """Test reading non-existent handoff file raises error."""
        with pytest.raises(Exception):  # UserError
            handoff_service.read_current_handoff()
