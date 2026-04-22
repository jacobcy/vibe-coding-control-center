"""Tests for TaskService with a fresh database."""

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.task_service import TaskService


@pytest.fixture(autouse=True)
def stable_flow_actor(monkeypatch):
    """Avoid real git identity lookups during issue-link tests."""
    monkeypatch.setattr(
        "vibe3.services.task_service.SignatureService.resolve_for_branch",
        lambda store, branch, explicit_actor=None: explicit_actor or "test-actor",
    )
    monkeypatch.setattr(
        "vibe3.services.flow_read_mixin.GitHubClient.get_pr",
        lambda self, pr_number=None, branch=None: None,
    )


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
    status = service._flow_service.get_flow_status("task/test")
    assert status.task_issue_number == 220


def test_reclassify_issue_moves_task_link_to_related_on_fresh_db(tmp_path):
    """Verify issue role reclassification updates hydrated task truth."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    store.update_flow_state("debug/vibe-server-fix", flow_slug="debug-vibe-server-fix")
    service.link_issue("debug/vibe-server-fix", 467, role="task")

    result = service.reclassify_issue(
        "debug/vibe-server-fix",
        467,
        old_role="task",
        new_role="related",
    )

    assert result.issue_role == "related"
    links = store.get_issue_links("debug/vibe-server-fix")
    assert any(
        link["issue_number"] == 467 and link["issue_role"] == "related"
        for link in links
    )
    assert not any(
        link["issue_number"] == 467 and link["issue_role"] == "task" for link in links
    )

    status = service._flow_service.get_flow_status("debug/vibe-server-fix")
    assert status.task_issue_number is None


def test_link_task_demotes_previous_task_flow_on_fresh_db(tmp_path):
    """Binding a new task flow should demote older task flows to related."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))

    store.update_flow_state("task/issue-467", flow_slug="issue-467", flow_status="done")
    store.add_issue_link("task/issue-467", 467, "task")
    store.update_flow_state("debug/new-attempt", flow_slug="new-attempt")

    class FakeGitHub:
        def list_prs_for_branch(self, branch: str, *, state: str | None = None):
            assert branch == "task/issue-467"
            _ = state
            return [
                PRResponse(
                    number=469,
                    title="PR 469",
                    body="",
                    state=PRState.MERGED,
                    head_branch="task/issue-467",
                    base_branch="main",
                    url="https://example.com/pr/469",
                )
            ]

        def view_issue(self, issue_number: int, repo: str | None = None):
            assert issue_number == 467
            assert repo == "owner/repo"
            return {
                "state": "open",
                "assignees": [{"login": "alice"}],
            }

        def remove_assignees(
            self,
            issue_number: int,
            assignees: list[str],
            repo: str | None = None,
        ) -> bool:
            assert issue_number == 467
            assert assignees == ["alice"]
            assert repo == "owner/repo"
            return True

        def add_comment(
            self,
            issue_number: int,
            body: str,
            repo: str | None = None,
        ) -> bool:
            assert issue_number == 467
            assert "PR #469" in body
            assert repo == "owner/repo"
            return True

    class FakeLabelPort:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, str]] = []

        def add_issue_label(self, issue_number: int, label: str) -> bool:
            self.calls.append(("add", issue_number, label))
            assert issue_number == 467
            assert label in {"supervisor", "state/handoff"}
            return True

        def get_issue_labels(self, issue_number: int):
            _ = issue_number
            return ["state/claimed"]

        def remove_issue_label(self, issue_number: int, label: str) -> bool:
            self.calls.append(("remove", issue_number, label))
            _ = issue_number
            assert label == "state/claimed"
            return True

        def ensure_label_exists(self, label: str, *, color: str, description: str):
            _ = label
            _ = color
            _ = description
            return True

    label_port = FakeLabelPort()
    service = TaskService(
        store=store,
        github_client=FakeGitHub(),
        issue_label_port=label_port,
        orchestra_config=OrchestraConfig(
            repo="owner/repo",
            supervisor_handoff=SupervisorHandoffConfig(issue_label="supervisor"),
        ),
    )

    service.link_issue("debug/new-attempt", 467, role="task")

    task_flows = store.get_flows_by_issue(467, role="task")
    related_flows = store.get_flows_by_issue(467, role="related")

    assert [flow["branch"] for flow in task_flows] == ["debug/new-attempt"]
    assert any(flow["branch"] == "task/issue-467" for flow in related_flows)
    assert ("add", 467, "supervisor") in label_port.calls
    assert ("add", 467, "state/handoff") in label_port.calls
    assert ("remove", 467, "state/claimed") in label_port.calls
