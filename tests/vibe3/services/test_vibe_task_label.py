"""Tests for vibe-task label auto-mirroring in TaskService."""

from unittest.mock import Mock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.task import TaskService


@pytest.fixture(autouse=True)
def stable_flow_actor(monkeypatch):
    """Avoid real git identity lookups during issue-link tests."""
    monkeypatch.setattr(
        "vibe3.services.task.service.SignatureService.resolve_for_branch",
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

    # Mock GitClient to return True for branch_exists
    monkeypatch.setattr(
        "vibe3.clients.git_client.GitClient",
        lambda: Mock(branch_exists=lambda branch: True),
    )

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


def test_link_issue_as_dependency_does_not_add_vibe_task_label(tmp_path, monkeypatch):
    """Verify that linking an issue as dependency role does NOT add vibe-task label."""
    db_path = tmp_path / "test.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    # Mock the label service
    mock_label_service = Mock()
    service._get_label_service = lambda: mock_label_service

    # Setup a flow
    store.update_flow_state("task/test-branch", flow_slug="test")

    # ACT: link issue as dependency
    service.link_issue("task/test-branch", 789, role="dependency")

    # ASSERT: confirm_vibe_task was NOT called
    mock_label_service.confirm_vibe_task.assert_not_called()


def test_link_issue_as_task_without_branch_does_not_add_label(tmp_path, monkeypatch):
    """Verify that linking issue as task without real branch does NOT add label."""
    db_path = tmp_path / "test.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    # Mock the label service
    mock_label_service = Mock()
    service._get_label_service = lambda: mock_label_service

    # Mock GitClient to return False for branch_exists
    monkeypatch.setattr(
        "vibe3.clients.git_client.GitClient",
        lambda: Mock(branch_exists=lambda branch: False),
    )

    # Setup a flow
    store.update_flow_state("task/test-branch", flow_slug="test")

    # ACT: link issue as task
    service.link_issue("task/test-branch", 999, role="task")

    # ASSERT: confirm_vibe_task was NOT called (no real branch)
    mock_label_service.confirm_vibe_task.assert_not_called()
