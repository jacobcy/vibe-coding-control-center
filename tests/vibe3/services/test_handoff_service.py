"""Tests for HandoffService."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.exceptions import UserError
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
    client.get_git_common_dir.return_value = "/tmp/test-common-dir"
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

    def test_ensure_current_handoff_creates_template(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that ensure_current_handoff creates template if not exists."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()

        assert handoff_path.exists()
        assert handoff_path.name == "current.md"
        content = handoff_path.read_text()
        assert "# Handoff: feature/test-branch" in content
        assert "lightweight handoff file" in content
        assert "## Summary" in content
        assert "## Findings" in content
        assert "## Blockers" in content
        assert "## Next Actions" in content
        assert "## Key Files" in content
        assert "## Evidence Refs" in content
        assert "## Updates" in content

    def test_ensure_current_handoff_existing_file_is_idempotent(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that existing file is returned without overwrite by default."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()
        original_content = handoff_path.read_text()

        handoff_path2 = handoff_service.ensure_current_handoff()
        assert handoff_path == handoff_path2
        assert handoff_path.read_text() == original_content

    def test_ensure_current_handoff_force_overwrites_existing_file(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that force=True rewrites existing file with fresh template."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()
        handoff_path.write_text("# Custom handoff\n")

        overwritten_path = handoff_service.ensure_current_handoff(force=True)

        assert overwritten_path == handoff_path
        assert "# Custom handoff" not in handoff_path.read_text()


class TestReadCurrentHandoff:
    """Tests for read_current_handoff method."""

    def test_read_current_handoff(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test reading current handoff file."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_service.ensure_current_handoff()

        content = handoff_service.read_current_handoff()
        assert "# Handoff: feature/test-branch" in content

    def test_read_current_handoff_not_found(self, handoff_service):
        """Test reading non-existent handoff file raises error."""
        with pytest.raises(UserError):
            handoff_service.read_current_handoff()


class TestAppendCurrentHandoff:
    """Tests for append_current_handoff method."""

    def test_append_current_handoff_creates_file_if_missing(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test append creates current.md when missing."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.append_current_handoff(
            message="Need to unify event taxonomy",
            actor="codex/gpt-5.4",
            kind="finding",
        )

        content = handoff_path.read_text()
        assert handoff_path.exists()
        assert "## Updates" in content
        assert "codex/gpt-5.4" in content
        assert "finding" in content
        assert "Need to unify event taxonomy" in content

    def test_append_current_handoff_appends_to_updates_section(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test append adds a new block at the end of updates."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        handoff_service.ensure_current_handoff()

        handoff_service.append_current_handoff(
            message="Blocked on GitHub Project mapping",
            actor="claude/sonnet-4.6",
            kind="blocker",
        )
        handoff_service.append_current_handoff(
            message="Next: define task sync contract",
            actor="codex/gpt-5.4",
            kind="next",
        )

        content = handoff_service.read_current_handoff()
        assert "Blocked on GitHub Project mapping" in content
        assert "Next: define task sync contract" in content
        assert content.index("Blocked on GitHub Project mapping") < content.index(
            "Next: define task sync contract"
        )


class TestGetHandoffDir:
    """Tests for _get_handoff_dir method - error handling and edge cases."""

    def test_get_handoff_dir_handles_permission_error(
        self, handoff_service, mock_git_client
    ):
        """Test that _get_handoff_dir raises SystemError on permission denied."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            mock_git_client.get_git_common_dir.return_value = str(git_dir)
            mock_git_client.get_current_branch.return_value = "feature/test"

            # Mock mkdir to raise PermissionError
            with patch.object(
                Path, "mkdir", side_effect=PermissionError("Permission denied")
            ):
                with pytest.raises(SystemError) as exc_info:
                    handoff_service._get_handoff_dir()

            assert "Failed to create handoff directory" in str(exc_info.value)
            assert "Permission denied" in str(exc_info.value)

    def test_get_handoff_dir_sanitizes_branch_name(
        self, handoff_service, mock_git_client
    ):
        """Test that _get_handoff_dir properly sanitizes branch names."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            mock_git_client.get_git_common_dir.return_value = str(git_dir)

            # Test branch with slashes and backslashes
            mock_git_client.get_current_branch.return_value = "feature/branch\\name"
            handoff_dir = handoff_service._get_handoff_dir()
            assert "branch-name" in str(handoff_dir)

            # Test branch starting with special chars
            mock_git_client.get_current_branch.return_value = "-branch-name"
            handoff_dir = handoff_service._get_handoff_dir()
            # Should strip leading special chars
            assert "branch-name" in str(handoff_dir)

            # Test branch ending with special chars
            mock_git_client.get_current_branch.return_value = "branch-name-"
            handoff_dir = handoff_service._get_handoff_dir()
            # Should strip trailing special chars
            assert "branch-name" in str(handoff_dir)

    def test_get_handoff_dir_handles_empty_branch_name(
        self, handoff_service, mock_git_client
    ):
        """Test that _get_handoff_dir handles branch names that become empty after sanitization."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            mock_git_client.get_git_common_dir.return_value = str(git_dir)

            # Test branch that becomes empty after sanitization
            mock_git_client.get_current_branch.return_value = "---"
            handoff_dir = handoff_service._get_handoff_dir()
            # Should use "default" fallback
            assert "default" in str(handoff_dir)
