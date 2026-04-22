"""Tests for handoff file operations."""

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


class TestEnsureCurrentHandoff:
    """Tests for ensure_current_handoff method."""

    def test_ensure_current_handoff_creates_template(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that ensure_current_handoff creates template if not exists."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()

        assert handoff_path.exists()
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

    def test_read_current_handoff(self, handoff_service, temp_git_dir, mock_git_client):
        """Test reading current handoff file."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_service.ensure_current_handoff()

        content = handoff_service.read_current_handoff()
        assert "# Handoff: feature/test-branch" in content

    def test_read_current_handoff_not_found(self, handoff_service):
        """Test reading non-existent handoff file raises error."""
        with pytest.raises(UserError):
            handoff_service.read_current_handoff()


class TestClearHandoffForBranch:
    """Tests for clearing branch handoff history."""

    def test_clear_handoff_for_branch_removes_directory(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_git_client.get_current_branch.return_value = "task/issue-329"

        handoff_path = handoff_service.ensure_current_handoff()
        assert handoff_path.exists()

        removed_dir = handoff_service.clear_handoff_for_branch("task/issue-329")

        assert removed_dir == handoff_path.parent
        assert not removed_dir.exists()


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

        content = handoff_service.read_current_handoff()
        assert "## Updates" in content
        assert "Blocked on GitHub Project mapping" in content
        assert "claude/sonnet-4.6" in content
        assert "blocker" in content


class TestGetHandoffDir:
    """Tests for _get_handoff_dir method."""

    def test_get_handoff_dir_sanitizes_branch_name(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that branch name is sanitized for use in directory path."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_git_client.get_current_branch.return_value = "feature/complex/branch/name"

        handoff_dir = handoff_service._get_handoff_dir()

        # Branch name should be sanitized and include hash suffix for uniqueness
        assert "feature-complex-branch-name" in str(handoff_dir)
        # Should have a hash suffix (8 hex chars)
        import re

        assert re.search(r"-[a-f0-9]{8}$", handoff_dir.name)
        assert handoff_dir.exists()

    def test_get_handoff_dir_handles_leading_trailing_dashes(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that leading/trailing dashes are stripped."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_git_client.get_current_branch.return_value = "-branch-with-dashes-"

        handoff_dir = handoff_service._get_handoff_dir()

        # Dashes should be stripped, with hash suffix added
        assert "branch-with-dashes" in str(handoff_dir)

    def test_get_handoff_dir_fallback_for_empty_name(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test fallback to 'default' when branch name sanitizes to empty."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_git_client.get_current_branch.return_value = "---"

        handoff_dir = handoff_service._get_handoff_dir()

        # Should use 'default' prefix with hash suffix
        assert "default" in str(handoff_dir)


class TestHandoffRecordAPIs:
    """Tests for record_plan, record_report, and record_audit methods."""

    def test_record_plan_persists_plan_ref_and_update_block(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ):
        """Test record_plan persists plan ref and update block."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        plan_ref = "docs/plans/feature-x.md"

        handoff_path = handoff_service.record_plan(
            plan_ref=plan_ref,
            next_step="Implement core logic",
            blocked_by=None,
            actor="test-actor",
        )

        assert handoff_path.exists()
        content = handoff_path.read_text()
        assert plan_ref in content
        assert "Implement core logic" in content
        assert "test-actor" in content
        assert "plan" in content.lower()

        # Verify flow state update
        mock_store.update_flow_state.assert_called_with(
            "feature/test-branch",
            plan_ref=plan_ref,
            planner_actor="test-actor",
            next_step="Implement core logic",
        )

    def test_record_report_persists_report_ref_and_update_block(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ):
        """Test record_report persists report ref and update block."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        report_ref = ".agent/reports/test-report.md"

        handoff_path = handoff_service.record_report(
            report_ref=report_ref,
            next_step="Review findings",
            blocked_by="Missing data",
            actor="test-actor",
        )

        assert handoff_path.exists()
        content = handoff_path.read_text()
        assert report_ref in content
        assert "Review findings" in content
        assert "Missing data" in content
        assert "test-actor" in content
        assert "report" in content.lower()

        # Verify flow state update
        mock_store.update_flow_state.assert_called_with(
            "feature/test-branch",
            report_ref=report_ref,
            executor_actor="test-actor",
            next_step="Review findings",
            blocked_by="Missing data",
        )

    def test_record_audit_persists_audit_ref_and_update_block(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ):
        """Test record_audit persists audit ref and update block."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        audit_ref = ".agent/reports/audit-result.md"

        handoff_path = handoff_service.record_audit(
            audit_ref=audit_ref,
            next_step="Finalize PR",
            blocked_by=None,
            actor="test-actor",
        )

        assert handoff_path.exists()
        content = handoff_path.read_text()
        assert audit_ref in content
        assert "Finalize PR" in content
        assert "test-actor" in content
        assert "audit" in content.lower()

        # Verify flow state update
        mock_store.update_flow_state.assert_called_with(
            "feature/test-branch",
            audit_ref=audit_ref,
            reviewer_actor="test-actor",
            next_step="Finalize PR",
        )

    def test_record_audit_updates_flow_state_without_event_recording(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ):
        """Test record_audit updates flow state and records event with verdict."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_service.record_audit(
            audit_ref=".agent/reports/audit-result.md",
            next_step="Finalize PR",
            blocked_by=None,
            actor="test-actor",
        )

        # _record_ref now calls add_event to record verdict
        mock_store.add_event.assert_called_once()
        call_args = mock_store.add_event.call_args
        assert call_args[0][0] == "feature/test-branch"
        # Default record_audit (not system-auto) records as handoff_audit.
        # Only is_system_auto=True produces audit_recorded.
        assert call_args[0][1] == "handoff_audit"
        assert call_args[0][2] == "test-actor"
        assert "verdict: UNKNOWN" in call_args[1]["detail"]
        assert call_args[1]["refs"]["ref"] == ".agent/reports/audit-result.md"

        mock_store.update_flow_state.assert_called_with(
            "feature/test-branch",
            audit_ref=".agent/reports/audit-result.md",
            reviewer_actor="test-actor",
            next_step="Finalize PR",
        )

    def test_record_audit_treats_handoff_file_append_as_best_effort(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store, monkeypatch
    ):
        """Test record_audit keeps authoritative writes when current.md append fails."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        def fail_append(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(handoff_service, "append_current_handoff", fail_append)

        handoff_path = handoff_service.record_audit(
            audit_ref=".agent/reports/audit-result.md",
            next_step="Finalize PR",
            blocked_by=None,
            actor="test-actor",
        )

        assert handoff_path.exists()
        # add_event is called to record verdict
        mock_store.add_event.assert_called_once()
        mock_store.update_flow_state.assert_called_once_with(
            "feature/test-branch",
            audit_ref=".agent/reports/audit-result.md",
            reviewer_actor="test-actor",
            next_step="Finalize PR",
        )

    def test_record_audit_persists_event_even_when_audit_ref_already_exists(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ):
        """Agent-authored audit_ref should still get authoritative event recording."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_store.get_flow_state.return_value = {
            "audit_ref": "docs/reports/agent-authored-audit.md"
        }

        handoff_service.record_audit(
            audit_ref="docs/reports/agent-authored-audit.md",
            actor="test-actor",
            verdict="PASS",
        )

        mock_store.update_flow_state.assert_called_with(
            "feature/test-branch",
            audit_ref="docs/reports/agent-authored-audit.md",
            reviewer_actor="test-actor",
        )
        mock_store.add_event.assert_called_once()
        call_args = mock_store.add_event.call_args
        # Agent-authored audit uses handoff_audit (not system-auto).
        assert call_args[0][1] == "handoff_audit"
        assert call_args[1]["refs"]["ref"] == "docs/reports/agent-authored-audit.md"
        assert call_args[1]["refs"]["verdict"] == "PASS"

    def test_record_audit_normalizes_absolute_ref_within_branch_worktree(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ):
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        branch_root = Path("/tmp/feature-test-branch")
        mock_git_client.find_worktree_path_for_branch.return_value = branch_root
        absolute_ref = str(branch_root / "docs" / "reports" / "audit.md")

        handoff_service.record_audit(
            audit_ref=absolute_ref,
            actor="test-actor",
            verdict="PASS",
        )

        mock_store.update_flow_state.assert_called_with(
            "feature/test-branch",
            audit_ref="docs/reports/audit.md",
            reviewer_actor="test-actor",
        )
        call_args = mock_store.add_event.call_args
        assert call_args[1]["refs"]["ref"] == "docs/reports/audit.md"


class TestRecordIndicateAction:
    """Tests for record_indicate latest_indicate_action persistence."""

    def test_record_indicate_with_action_writes_indicate_action(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ) -> None:
        """record_indicate --action commit_pr must write latest_indicate_action."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_service.record_indicate(
            indicate_ref="docs/indicate/manager-indicate.md",
            actor="manager",
            action="commit_pr",
        )

        # update_flow_state should have been called twice:
        # 1st for flow_updates (indicate_ref, etc.), 2nd for latest_indicate_action
        calls = mock_store.update_flow_state.call_args_list
        # Find the call that sets latest_indicate_action
        action_call = next(
            (c for c in calls if "latest_indicate_action" in c.kwargs),
            None,
        )
        assert action_call is not None, "latest_indicate_action must be written"
        assert action_call.kwargs["latest_indicate_action"] == "commit_pr"

    def test_record_indicate_without_action_clears_indicate_action(
        self, handoff_service, temp_git_dir, mock_git_client, mock_store
    ) -> None:
        """record_indicate without --action must clear latest_indicate_action (None)."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_service.record_indicate(
            indicate_ref="docs/indicate/manager-indicate.md",
            actor="manager",
            action=None,  # No action → clear
        )

        calls = mock_store.update_flow_state.call_args_list
        action_call = next(
            (c for c in calls if "latest_indicate_action" in c.kwargs),
            None,
        )
        assert action_call is not None, "latest_indicate_action must always be written"
        assert (
            action_call.kwargs["latest_indicate_action"] is None
        ), "latest_indicate_action must be cleared (None) when no action provided"
