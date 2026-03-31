"""Tests for TaskService with a fresh database."""

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.task_service import TaskService


def test_link_issue_task_on_fresh_db(tmp_path):
    """Verify that linking a task issue works on a fresh DB."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    # Setup a flow
    store.update_flow_state("task/test", flow_slug="test")

    # ACT: link issue as task
    # This used to write task_issue_number to flow_state.
    # Now it should only use flow_issue_links.
    service.link_issue("task/test", 220, role="task")

    # ASSERT
    links = store.get_issue_links("task/test")
    assert any(
        link["issue_number"] == 220 and link["issue_role"] == "task" for link in links
    )

    # Hydrate should find it
    status = service.get_flow_status("task/test")
    assert status.task_issue_number == 220
