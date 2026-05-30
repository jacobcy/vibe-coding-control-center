"""Tests for vibe-task label auto-mirroring in TaskService."""

from unittest.mock import Mock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.task_service import TaskService


@pytest.fixture(autouse=True)
def stable_flow_actor(monkeypatch):
    """Avoid real git identity lookups during issue-link tests."""
    monkeypatch.setattr(
        "vibe3.services.task_service.SignatureService.resolve_for_branch",
        lambda store, branch, explicit_actor=None: explicit_actor or "test-actor",
    )


def test_link_issue_as_task_adds_vibe_task_label(tmp_path, monkeypatch):
    """Verify that linking an issue as task role auto-adds vibe-task label."""
    db_path = tmp_path / "test.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    # Mock the label service
    mock_label_service = Mock()
    mock_label_service.confirm_vibe_task.return_value = "advanced"
    service._get_label_service = lambda: mock_label_service

    # Setup a flow
    store.update_flow_state("task/test-branch", flow_slug="test")

    # ACT: link issue as task
    service.link_issue("task/test-branch", 123, role="task")

    # ASSERT: confirm_vibe_task was called with should_exist=True
    mock_label_service.confirm_vibe_task.assert_called_once_with(123, should_exist=True)


def test_link_issue_as_related_does_not_add_vibe_task_label(tmp_path, monkeypatch):
    """Verify that linking an issue as related role does NOT add vibe-task label."""
    db_path = tmp_path / "test.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    # Mock the label service
    mock_label_service = Mock()
    service._get_label_service = lambda: mock_label_service

    # Setup a flow
    store.update_flow_state("task/test-branch", flow_slug="test")

    # ACT: link issue as related
    service.link_issue("task/test-branch", 456, role="related")

    # ASSERT: confirm_vibe_task was NOT called
    mock_label_service.confirm_vibe_task.assert_not_called()


def test_reclassify_from_task_to_related_removes_vibe_task_label(tmp_path, monkeypatch):
    """Verify that reclassifying from task to related removes vibe-task label."""
    db_path = tmp_path / "test.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    # Mock the label service
    mock_label_service = Mock()
    service._get_label_service = lambda: mock_label_service

    # Setup: create flow with task issue
    store.update_flow_state("task/test-branch", flow_slug="test")
    service.link_issue("task/test-branch", 789, role="task")

    # Reset mock to check the reclassify call
    mock_label_service.reset_mock()

    # ACT: reclassify from task to related
    service.reclassify_issue(
        "task/test-branch",
        789,
        old_role="task",
        new_role="related",
    )

    # ASSERT: confirm_vibe_task was called with should_exist=False
    mock_label_service.confirm_vibe_task.assert_called_once_with(
        789, should_exist=False
    )


def test_reclassify_from_related_to_task_adds_vibe_task_label(tmp_path, monkeypatch):
    """Verify that reclassifying from related to task adds vibe-task label."""
    db_path = tmp_path / "test.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    # Mock the label service
    mock_label_service = Mock()
    service._get_label_service = lambda: mock_label_service

    # Setup: create flow with related issue
    store.update_flow_state("task/test-branch", flow_slug="test")
    service.link_issue("task/test-branch", 999, role="related")

    # Reset mock to check the reclassify call
    mock_label_service.reset_mock()

    # ACT: reclassify from related to task
    service.reclassify_issue(
        "task/test-branch",
        999,
        old_role="related",
        new_role="task",
    )

    # ASSERT: confirm_vibe_task was called with should_exist=True
    mock_label_service.confirm_vibe_task.assert_called_once_with(999, should_exist=True)
