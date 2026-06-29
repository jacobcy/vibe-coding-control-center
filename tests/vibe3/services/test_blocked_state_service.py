"""Integration tests for BlockedStateService triple-state consistency."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

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

    def view_issue(self, issue_number: int) -> dict:
        return {
            "labels": [{"name": label} for label in self._labels],
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

    service.block(
        branch="test-branch",
        reason=None,
        blocked_by_issue=456,
        actor="executor/agent",
        issue_number=123,
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


def test_block_rejects_reason_and_dependency_together(tmp_path: Path) -> None:
    """Reason and dependency metadata should remain mutually exclusive."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    service = BlockedStateService(store=store, github_client=StubGitHubClient())

    with pytest.raises(ValueError, match="mutually exclusive"):
        service.block(
            branch="test-branch",
            reason="Manual block",
            blocked_by_issue=456,
            actor="executor/agent",
            issue_number=123,
        )


def test_unblock_clears_all_three_sources(tmp_path: Path) -> None:
    """Verify unblock() clears database, issue body, and labels."""
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

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    service.unblock(
        branch="test-branch",
        target_state=IssueState.READY,
        actor="human:resume",
        issue_number=123,
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


def test_sync_cache_from_truth_aligns_database(tmp_path: Path) -> None:
    """Verify sync_cache_from_truth() aligns database to issue body truth."""
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

    service = BlockedStateService(
        store=store,
        github_client=github,
    )

    state = service.sync_cache_from_truth("test-branch", 123)

    # Verify state from truth
    assert state.is_blocked
    assert state.blocked_reason == "Remote truth"

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

    service = BlockedStateService(
        store=store,
        github_client=github,
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


def test_block_handles_missing_issue_number(tmp_path: Path) -> None:
    """Verify block() works without issue_number (skips body/label writes)."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    service = BlockedStateService(store=store)

    service.block(
        branch="test-branch",
        reason="No issue linked",
        actor="system",
        issue_number=None,
    )

    # Database still written
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") == "No issue linked"


def test_block_respects_state_machine_on_double_block(tmp_path: Path) -> None:
    """Verify block() handles already-blocked label gracefully without force=True."""
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

    # Should not raise even though BLOCKED → BLOCKED is not in ALLOWED_TRANSITIONS
    service.block(
        branch="test-branch",
        reason="Second failure",
        actor="system",
        issue_number=123,
    )

    # DB and body still written; label stays BLOCKED
    flow_state = store.get_flow_state("test-branch")
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") == "Second failure"


def test_unblock_returns_result_with_label_status(tmp_path: Path) -> None:
    """unblock() should return UnblockResult with label_cleared status."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="Previous error",
    )

    github = StubGitHubClient()
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    svc = BlockedStateService(
        store=store, github_client=github, label_service=label_service
    )
    result = svc.unblock(
        branch="test-branch",
        target_state=IssueState.READY,
        issue_number=123,
        detail="test",
    )
    assert hasattr(result, "label_cleared")
    assert result.label_cleared is True


def test_unblock_reports_label_failure(tmp_path: Path) -> None:
    """unblock() should report when label write fails."""
    from unittest.mock import MagicMock

    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="Previous error",
    )

    github = StubGitHubClient()
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    svc = BlockedStateService(
        store=store, github_client=github, label_service=label_service
    )
    # Make label write fail
    svc._io.write_label_state = MagicMock(side_effect=Exception("API error"))

    result = svc.unblock(
        branch="test-branch",
        target_state=IssueState.READY,
        issue_number=123,
    )
    assert result.label_cleared is False
    assert label_service.current_state == IssueState.BLOCKED


def test_remove_issue_link(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.add_issue_link("test-branch", 101, "dependency")
    links_before = store.get_dependency_links("test-branch")
    assert 101 in links_before

    store.remove_issue_link("test-branch", 101, "dependency")
    links_after = store.get_dependency_links("test-branch")
    assert 101 not in links_after

