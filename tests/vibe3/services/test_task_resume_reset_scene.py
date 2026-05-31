"""Tests for reset_task_scene operation."""

from unittest.mock import MagicMock, patch

from tests.vibe3.services.conftest import _make_operations


def test_reset_task_scene_deletes_branch_handoff_and_flow_truth() -> None:
    """Test that reset_task_scene uses FlowCleanupService for complete cleanup."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        operations.reset_task_scene("task/issue-329")

        # Verify FlowCleanupService was instantiated
        mock_cleanup_cls.assert_called_once()

        # Verify cleanup_flow_scene was called with correct parameters
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-329",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,  # Resume always deletes flow record
            force_delete=False,  # Default: soft delete for audit trail
        )


def test_reset_task_scene_creates_tombstone_after_full_rebuild() -> None:
    """Test that reset_task_scene calls cleanup service for tombstone creation."""
    operations = _make_operations()

    branch = "task/issue-999"

    # Mock FlowCleanupService to make test hermetic
    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_class:
        mock_cleanup_service = MagicMock()
        mock_cleanup_class.return_value = mock_cleanup_service

        # Setup cleanup result
        mock_cleanup_service.cleanup_flow_scene.return_value = {
            "tmux_sessions": {"success": True, "sessions": []},
            "worktree": {"success": True, "path": None},
            "local_branch": {"success": True, "deleted": True},
            "remote_branch": {"success": True, "deleted": True},
            "handoff_files": {"success": True, "files": []},
            "flow_record": {"success": True, "deleted": True},
        }

        # Execute reset
        operations.reset_task_scene(branch)

        # Verify cleanup_flow_scene called with correct parameters
        mock_cleanup_service.cleanup_flow_scene.assert_called_once_with(
            branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=False,  # Default: soft delete for audit trail
        )

        # Note: Tombstone normalization is validated in repository tests
        # This test verifies the call path through FlowCleanupService


def test_reset_task_scene_with_remote_keeps_remote_branch() -> None:
    """Test reset_task_scene with include_remote=False (--remote mode)."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,  # Though we're keeping it
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Call with include_remote=False (--remote mode)
        operations.reset_task_scene("task/issue-123", include_remote=False)

        # Verify FlowCleanupService was instantiated
        mock_cleanup_cls.assert_called_once()

        # Verify cleanup_flow_scene was called with include_remote=False
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-123",
            include_remote=False,  # Key assertion: keep remote branch
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=False,  # Default: soft delete for audit trail
        )


def test_reset_task_scene_with_force_delete_true() -> None:
    """Test reset_task_scene with force_delete=True (hard delete for rebuild)."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Call with force_delete=True (PR closed / resume all scenario)
        operations.reset_task_scene("task/issue-1719", force_delete=True)

        # Verify cleanup_flow_scene was called with force_delete=True
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-1719",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=True,  # Key assertion: hard delete for rebuild
        )


def test_reset_task_scene_with_force_delete_false_default() -> None:
    """Test reset_task_scene defaults to force_delete=False (soft delete for audit)."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Call without force_delete (default behavior)
        operations.reset_task_scene("task/issue-123")

        # Verify cleanup_flow_scene was called with force_delete=False
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-123",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=False,  # Key assertion: soft delete for audit trail
        )


def test_soft_delete_then_create_flow_produces_clean_state() -> None:
    """Full cycle: soft_delete -> create_flow must produce a clean active flow.

    Simulates the orchestra dispatch after PR-closed reset:
    1. Soft-delete the flow (as cleanup does)
    2. Create a new flow (as orchestra dispatch does)
    3. Verify: deleted_at is NULL, flow_status is 'active', no zombie links
    """
    import tempfile
    from pathlib import Path

    from vibe3.clients.sqlite_client import SQLiteClient

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Setup: create flow with links and session
        store.update_flow_state(
            "task/issue-100",
            flow_slug="issue-100",
            flow_status="active",
        )
        store.add_issue_link("task/issue-100", 100, "task")

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runtime_session "
            "(role, target_type, target_id, branch, session_name, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            ("planner", "issue", "100", "task/issue-100", "sess-1", "running"),
        )
        conn.commit()

        # Step 1: Soft delete (as cleanup does)
        store.soft_delete_flow("task/issue-100")

        # Verify tombstone
        tombstone = store.get_flow_state_include_deleted("task/issue-100")
        assert tombstone is not None
        assert tombstone["deleted_at"] is not None
        assert tombstone["flow_status"] == "aborted"

        # Verify cascade: runtime_session and flow_issue_links are gone
        cursor.execute(
            "SELECT COUNT(*) FROM runtime_session WHERE branch = ?",
            ("task/issue-100",),
        )
        assert cursor.fetchone()[0] == 0

        cursor.execute(
            "SELECT COUNT(*) FROM flow_issue_links WHERE branch = ?",
            ("task/issue-100",),
        )
        assert cursor.fetchone()[0] == 0

        # Step 2: Simulate what create_flow does with tombstone
        store.restore_flow("task/issue-100")
        store.update_flow_state("task/issue-100", flow_status="active")

        # Step 3: Verify clean state
        active = store.get_flow_state("task/issue-100")
        assert active is not None, "get_flow_state must find the restored flow"
        assert active["deleted_at"] is None
        assert active["flow_status"] == "active"
