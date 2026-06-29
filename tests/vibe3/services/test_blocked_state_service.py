"""Integration tests for BlockedStateService triple-state consistency."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestration import IssueState
from vibe3.services.flow.blocked_state_service import (
    BlockedStateService,
)


class StubGitHubClient:
    def __init__(self, issue_body: str = "", labels: list[str] | None = None):
        self._issue_body = issue_body
        self._labels = labels or []

    def get_issue_body(self, issue_number: int) -> str | None:
        return self._issue_body

    def update_issue_body(self, issue_number: int, body: str) -> bool:
        self._issue_body = body
        return True

    def view_issue(self, issue_number: int, *args, **kwargs) -> dict:
        return {
            "labels": [{"name": label} for label in self._labels],
            "state": "OPEN",  # Default to OPEN to simulate unresolved dependency
        }


class StubLabelService:
    def __init__(self):
        self.current_state = None

    def confirm_issue_state(
        self, issue_number: int, state: IssueState, actor: str, force: bool = False
    ) -> str:
        """Return values matching real LabelService.confirm_issue_state behavior."""
        if self.current_state == state:
            return "confirmed"
        self.current_state = state
        return "advanced"

    def get_state(self, issue_number: int) -> IssueState | None:
        return self.current_state


def test_block_dependency_writes_to_all_three_sources(tmp_path: Path) -> None:
    """Verify dependency block writes to database, issue body, and labels."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    github = StubGitHubClient()
    label_service = StubLabelService()

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    service.set_block(
        issue_number=123,
        branch="test-branch",
        reason=None,
        tasks=[456],
        actor="executor/agent",
    )

    # Verify database
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") is None
    assert flow_state.get("blocked_by_issue") == 456

    # Verify issue body
    assert "blocked" in github._issue_body.lower()
    assert "- **Blocked by**: #456" in github._issue_body

    # Verify label
    assert label_service.current_state == IssueState.BLOCKED


def test_block_accepts_reason_and_dependency_together(tmp_path: Path) -> None:
    """Reason and dependency metadata can be set together."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient()
    label_service = StubLabelService()

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    service.set_block(
        issue_number=123,
        branch="test-branch",
        reason="Manual block",
        tasks=[456],
        actor="executor/agent",
    )

    # Verify database
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") == "Manual block"
    assert flow_state.get("blocked_by_issue") == 456


def test_unblock_clears_all_three_sources(tmp_path: Path) -> None:
    """Verify clear_block() clears database, issue body, and labels."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="Previous error",
        blocked_by_issue=789,
    )

    issue_body_blocked = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n"
        "- **Blocked reason**: Previous error\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(
        issue_body=issue_body_blocked,
        labels=["state/blocked"],
    )
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    service.clear_block(
        issue_number=123,
        branch="test-branch",
        clear_reason=True,
        actor="human:resume",
    )

    # Verify database cleared
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "active"
    assert flow_state.get("blocked_reason") is None
    assert flow_state.get("blocked_by_issue") is None

    # Verify issue body cleared
    assert (
        "blocked" not in github._issue_body.lower()
        or "blocked_by: []" in github._issue_body
    )

    # Verify label changed
    assert label_service.current_state == IssueState.READY


def test_reconcile_blocked_aligns_database(tmp_path: Path) -> None:
    """Verify reconcile_blocked() aligns database to issue body truth."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="active",
    )

    issue_body_remote = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n"
        "- **Blocked reason**: Remote truth\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(
        issue_body=issue_body_remote,
    )
    label_service = StubLabelService()

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    service.reconcile_blocked(123, "test-branch")

    # Verify database synced to truth
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") == "Remote truth"


def test_validate_consistency_detects_mismatch(tmp_path: Path) -> None:
    """Verify validate_consistency() detects state mismatches."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="DB says blocked",
    )

    issue_body_active = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: active\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(
        issue_body=issue_body_active,
        labels=[],
    )
    label_service = StubLabelService()

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    report = service.validate_consistency("test-branch", 123)

    # Verify inconsistency detected
    assert not report.is_consistent
    assert report.database_state.is_blocked
    assert not report.body_state.is_blocked
    assert report.authoritative_state == report.body_state


def test_resolve_truth_reads_from_issue_body_first(tmp_path: Path) -> None:
    """Verify resolve_truth() reads issue body before database."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="active",
    )

    issue_body_truth = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n"
        "- **Blocked reason**: Body truth\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(
        issue_body=issue_body_truth,
    )

    service = BlockedStateService(
        store=store,
        github_client=github,
    )

    state = service.resolve_truth("test-branch", 123)

    # Body truth prevails
    assert state.is_blocked
    assert state.blocked_reason == "Body truth"


def test_resolve_truth_fallback_to_database_on_github_failure(tmp_path: Path) -> None:
    """Verify resolve_truth() falls back to database when GitHub fails."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="DB cache truth",
    )

    github = MagicMock()
    github.get_issue_body.side_effect = Exception("GitHub API error")

    service = BlockedStateService(
        store=store,
        github_client=github,
    )

    state = service.resolve_truth("test-branch", 123)

    # Fallback to database
    assert state.is_blocked
    assert state.blocked_reason == "DB cache truth"


def test_set_block_on_double_block(tmp_path: Path) -> None:
    """Verify set_block() handles already-blocked label gracefully."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    github = StubGitHubClient()
    label_service = StubLabelService()
    # Simulate issue already in BLOCKED state
    label_service.current_state = IssueState.BLOCKED

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    # Should not raise even though BLOCKED -> BLOCKED is called
    service.set_block(
        issue_number=123,
        branch="test-branch",
        reason="Second failure",
        actor="system",
    )

    # DB and body still written; label stays BLOCKED
    flow_state = store.get_flow_state("test-branch")
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") == "Second failure"


def test_remove_issue_link(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.add_issue_link("test-branch", 101, "dependency")
    links_before = store.get_dependency_links("test-branch")
    assert 101 in links_before

    store.remove_issue_link("test-branch", 101, "dependency")
    links_after = store.get_dependency_links("test-branch")
    assert 101 not in links_after


def test_parse_projection_merges_legacy_dependencies() -> None:
    from vibe3.services.issue.body import parse_projection

    legacy_body = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n"
        "- **Blocked by**: #456\n"
        "- **Dependencies**: #789, #101\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    proj = parse_projection(legacy_body)
    # Check that legacy dependencies are merged into blocked_by
    assert sorted(proj.blocked_by) == [101, 456, 789]
    # Check that dependencies attribute is retired
    assert not hasattr(proj, "dependencies")


def test_reconcile_blocked_blocked_state(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    # Body has a blocked reason
    issue_body_blocked = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n"
        "- **Blocked reason**: Blocked by human\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(issue_body=issue_body_blocked)
    label_service = StubLabelService()

    svc = BlockedStateService(
        store=store, github_client=github, label_service=label_service
    )

    # Reconcile should keep state blocked
    target = svc.reconcile_blocked(123, "test-branch")
    assert target is None
    assert label_service.current_state == IssueState.BLOCKED
    assert store.get_flow_state("test-branch").get("flow_status") == "blocked"


def test_reconcile_blocked_resume_state(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    issue_body_blocked = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n"
        "- **Blocked reason**: Blocked by human\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(issue_body=issue_body_blocked)
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    svc = BlockedStateService(
        store=store, github_client=github, label_service=label_service
    )

    # Reconcile with clear_reason=True should unblock and resume to READY
    target = svc.reconcile_blocked(123, "test-branch", clear_reason=True)
    assert target == IssueState.READY
    assert label_service.current_state == IssueState.READY
    assert store.get_flow_state("test-branch").get("flow_status") == "active"


def test_reconcile_blocked_dependency_resolved(tmp_path: Path) -> None:
    """When a dependency is resolved, reconcile_blocked unblocks the flow."""
    from unittest.mock import patch

    from vibe3.services.shared.dependency_resolution import DependencyResolution

    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_by_issue=456,
    )
    store.add_issue_link("test-branch", 456, "dependency")

    issue_body_blocked = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n"
        "- **Blocked by**: #456\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(issue_body=issue_body_blocked)
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    svc = BlockedStateService(
        store=store, github_client=github, label_service=label_service
    )

    # Mock DependencyResolutionService.is_dependency_resolved to return resolved=True
    with patch(
        "vibe3.services.shared.dependency_resolution.DependencyResolutionService.is_dependency_resolved"
    ) as mock_resolved:
        mock_resolved.return_value = DependencyResolution(
            resolved=True,
            issue_number=456,
            github_state="CLOSED",
        )

        target = svc.reconcile_blocked(123, "test-branch")

    # Verify reconciliation unblocked the flow and updated target
    assert target == IssueState.READY
    assert label_service.current_state == IssueState.READY

    # Verify database flow_state cache is updated
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "active"
    assert flow_state.get("blocked_by_issue") is None

    # Verify database flow_issue_links cache is cleared
    links = store.get_dependency_links("test-branch")
    assert 456 not in links
    assert len(links) == 0


def test_reconcile_degraded_stays_blocked(tmp_path: Path) -> None:
    """Degraded mode (GitHub read fails) must not be misjudged as "recovered".

    When GitHub is unreachable, reconcile_blocked returns None (conservative
    block) and must NOT rebuild the cache or flip flow_status to active.
    """
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "task/issue-100",
        flow_slug="issue-100",
        flow_status="blocked",
        blocked_reason="Manual intervention",
    )

    github = MagicMock()
    github.get_issue_body.side_effect = Exception("GitHub API unavailable")

    svc = BlockedStateService(store=store, github_client=github)

    target = svc.reconcile_blocked(
        100, "task/issue-100", clear_reason=False, actor="orchestra:dispatcher"
    )

    # None = stay blocked, caller must not interpret as recovered
    assert target is None

    # flow_status must NOT have been flipped to active during degraded mode
    flow_state = store.get_flow_state("task/issue-100")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
