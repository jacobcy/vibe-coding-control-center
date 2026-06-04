"""Tests for TaskService with a fresh database."""

import os
from unittest.mock import MagicMock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import InvalidBranchLinkError
from vibe3.models.flow import FlowStatusResponse
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

    mock_gh = MagicMock()
    mock_gh.get_pr.return_value = None

    monkeypatch.setattr(
        "vibe3.services.flow_read_mixin.GitHubClient",
        lambda: mock_gh,
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


def test_link_task_demotes_previous_task_flow_on_fresh_db(tmp_path, monkeypatch):
    """Binding a new task flow should demote older task flows to related."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))

    # Mock GitClient to return True for branch_exists (for vibe-task label auto-mirror)
    monkeypatch.setattr(
        "vibe3.clients.git_client.GitClient",
        lambda: type(
            "MockGitClient", (), {"branch_exists": lambda self, branch: True}
        )(),
    )

    store.update_flow_state("task/issue-467", flow_slug="issue-467", flow_status="done")
    store.add_issue_link("task/issue-467", 467, "task")
    store.update_flow_state("debug/new-attempt", flow_slug="new-attempt")

    class FakeGitHub:
        def list_prs_for_branch(
            self, branch: str, *, state: str | None = None, repo: str | None = None
        ):
            assert branch == "task/issue-467"
            _ = state, repo
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

        def list_all_prs(
            self, *, state: str = "all", limit: int = 50, repo: str | None = None
        ):
            """Return all PRs for recent PR cache."""
            _ = state, limit, repo
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
            assert label in {"supervisor", "state/handoff", "vibe-task"}
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
    assert ("add", 467, "vibe-task") in label_port.calls  # Auto-mirrored
    assert ("remove", 467, "state/claimed") in label_port.calls


def _create_ref_files(notes_dir, plan_ref, report_ref, audit_ref):
    """Create ref files with mtimes ensuring report > audit > plan for fallback."""
    if plan_ref:
        f = notes_dir / "plan.md"
        f.write_text("# Plan", encoding="utf-8")
        os.utime(f, (1, 1))
    if audit_ref:
        f = notes_dir / "audit.md"
        f.write_text("# Audit", encoding="utf-8")
        os.utime(f, (2, 2))
    if report_ref:
        f = notes_dir / "report.md"
        f.write_text("# Report", encoding="utf-8")
        os.utime(f, (3, 3))


def test_select_latest_ref_prefers_newer_valid_authoritative_ref(tmp_path) -> None:
    """Quick view should prefer the latest valid ref by mtime when no role is 'done'."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    audit_ref = notes_dir / "audit.md"
    report_ref = notes_dir / "report.md"
    audit_ref.write_text("# Audit\n旧审查结论", encoding="utf-8")
    report_ref.write_text(
        "# Report\n最新一轮已经修好 reviewer 之前的问题",
        encoding="utf-8",
    )

    os.utime(audit_ref, (1, 1))
    os.utime(report_ref, (2, 2))

    # Explicitly set statuses to non-"done" to test mtime fallback path
    flow = FlowStatusResponse(
        branch="task/issue-501",
        flow_slug="issue-501",
        flow_status="active",
        task_issue_number=501,
        planner_status="running",
        executor_status="running",
        reviewer_status=None,
        report_ref="notes/report.md",
        audit_ref="notes/audit.md",
        worktree_root=str(tmp_path),
    )

    summary = service._show_service._select_latest_ref("task/issue-501", flow)

    assert summary is not None
    assert summary.kind == "report"
    assert summary.ref == "notes/report.md"
    assert "最新一轮已经修好" in summary.summary


@pytest.mark.parametrize(
    "planner_status,executor_status,reviewer_status,plan_ref,report_ref,audit_ref,expected_kind,expected_ref",
    [
        # State transition scenarios: reviewer → executor → planner priority
        pytest.param(
            "running",
            None,
            None,
            "notes/plan.md",
            None,
            None,
            "plan",
            "notes/plan.md",
            id="planner_done_with_plan_ref",
        ),
        pytest.param(
            None,
            "done",
            None,
            None,
            "notes/report.md",
            None,
            "report",
            "notes/report.md",
            id="executor_done_with_report_ref",
        ),
        pytest.param(
            None,
            None,
            "done",
            None,
            None,
            "notes/audit.md",
            "audit",
            "notes/audit.md",
            id="reviewer_done_with_audit_ref",
        ),
        pytest.param(
            "done",
            "done",
            "done",
            "notes/plan.md",
            "notes/report.md",
            "notes/audit.md",
            "audit",
            "notes/audit.md",
            id="all_done_reviewer_priority",
        ),
        pytest.param(
            "pending",
            "done",
            "pending",
            "notes/plan.md",
            "notes/report.md",
            "notes/audit.md",
            "report",
            "notes/report.md",
            id="executor_done_others_pending",
        ),
        pytest.param(
            "done",
            "running",
            None,
            "notes/plan.md",
            "notes/report.md",
            None,
            "plan",
            "notes/plan.md",
            id="planner_done_executor_running",
        ),
        # Fallback scenarios: all non-done
        pytest.param(
            "running",
            None,
            "pending",
            None,
            "notes/report.md",
            "notes/audit.md",
            "report",
            "notes/report.md",
            id="fallback_two_refs_by_mtime",
        ),
        pytest.param(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            id="no_refs_returns_none",
        ),
    ],
)
def test_select_latest_ref_with_state_transitions(
    tmp_path,
    planner_status,
    executor_status,
    reviewer_status,
    plan_ref,
    report_ref,
    audit_ref,
    expected_kind,
    expected_ref,
) -> None:
    """Test _select_latest_ref state transition logic.

    When a role status is "done", the corresponding ref should be prioritized.
    Priority order: reviewer → executor → planner (reverse of execution order).
    Fallback to mtime when no role is "done".
    """
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(store=store)

    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    _create_ref_files(notes_dir, plan_ref, report_ref, audit_ref)

    flow = FlowStatusResponse(
        branch="task/issue-501",
        flow_slug="issue-501",
        flow_status="active",
        task_issue_number=501,
        planner_status=planner_status,
        executor_status=executor_status,
        reviewer_status=reviewer_status,
        plan_ref=plan_ref,
        report_ref=report_ref,
        audit_ref=audit_ref,
        worktree_root=str(tmp_path),
    )

    summary = service._show_service._select_latest_ref("task/issue-501", flow)

    if expected_kind is None:
        assert summary is None
    else:
        assert summary is not None
        assert summary.kind == expected_kind
        assert summary.ref == expected_ref


def test_link_issue_rejects_base_branch_main(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for base branch 'main'."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("main", 999, role="task")

    assert exc_info.value.branch == "main"
    assert exc_info.value.issue_number == 999
    assert "Invalid branch 'main'" in str(exc_info.value)
    assert "DELETE FROM flow_issue_links" in str(exc_info.value)


def test_link_issue_rejects_base_branch_master(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for base branch 'master'."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("master", 999, role="task")

    assert exc_info.value.branch == "master"
    assert exc_info.value.issue_number == 999


def test_link_issue_rejects_base_branch_develop(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for base branch 'develop'."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("develop", 999, role="task")

    assert exc_info.value.branch == "develop"
    assert exc_info.value.issue_number == 999


def test_link_issue_rejects_configured_base_branch(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for configured scene_base_ref."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/custom-base"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("custom-base", 999, role="task")

    assert exc_info.value.branch == "custom-base"
    assert exc_info.value.issue_number == 999


def test_link_issue_accepts_valid_branch(tmp_path, monkeypatch):
    """link_issue accepts valid task branch."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    store.update_flow_state("task/issue-999", flow_slug="issue-999")
    result = service.link_issue("task/issue-999", 999, role="task")

    assert result.branch == "task/issue-999"
    assert result.issue_number == 999
    assert result.issue_role == "task"
