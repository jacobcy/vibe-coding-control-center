"""Tests for BlockedStateService authority separation (#3289).

Covers the split API:
- ``sync_block_state``       — align cache/label to truth (no resume)
- ``evaluate_auto_eligibility`` — read-only eligibility + snapshot
- ``apply_auto_resume``      — consume snapshot-bound decision
- ``manual_resume``          — authorized clear + explicit/inferred target

Includes the mandatory truth table (#3289 acceptance criteria), the #3184
regression (durable human reason survives auto paths), and the race test
(stale decision rejected when truth changed between evaluate and apply).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState
from vibe3.services.flow.blocked_state_service import BlockedStateService
from vibe3.services.flow.blocked_state_types import (
    AutoResumeDecision,
    AutoResumeReasonCode,
    AutoResumeVerdict,
)
from vibe3.services.shared.dependency_resolution import DependencyResolution


class StubGitHubClient:
    """GitHub stub with body + updatedAt snapshot support."""

    def __init__(
        self,
        issue_body: str = "",
        labels: list[str] | None = None,
        updated_at: str = "2026-07-02T00:00:00Z",
    ) -> None:
        self._issue_body = issue_body
        self._labels = labels or []
        self._updated_at = updated_at
        self.updated_at_calls = 0

    def get_issue_body(self, issue_number: int) -> str | None:
        return self._issue_body

    def get_issue_snapshot(
        self, issue_number: int, repo: str | None = None
    ) -> tuple[str | None, str | None] | None:
        self.updated_at_calls += 1
        return (self._issue_body, self._updated_at)

    def update_issue_body(self, issue_number: int, body: str) -> bool:
        self._issue_body = body
        return True

    def view_issue(self, issue_number: int, *args, **kwargs) -> dict:
        # Default to OPEN so dependency checks show unresolved (matching the
        # original stub). Tests that need CLOSED deps patch
        # DependencyResolutionService.is_dependency_resolved directly.
        return {
            "labels": [
                {"name": label}
                for label in (self._labels if isinstance(self._labels, list) else [])
            ],
            "state": "OPEN",
        }


class StubLabelService:
    def __init__(self) -> None:
        self.current_state: IssueState | None = None

    def confirm_issue_state(
        self, issue_number: int, state: IssueState, actor: str, force: bool = False
    ) -> str:
        if self.current_state == state:
            return "confirmed"
        self.current_state = state
        return "advanced"

    def get_state(self, issue_number: int) -> IssueState | None:
        return self.current_state

    def replace_issue_state(
        self, issue_number: int, state: IssueState, *, actor: str
    ) -> str:
        self.current_state = state
        return "normalized"


class TrackingLabelService(StubLabelService):
    """Track all confirm_issue_state calls."""

    def __init__(self) -> None:
        super().__init__()
        self.confirm_calls: list[tuple[int, IssueState, str, bool]] = []

    def confirm_issue_state(
        self,
        issue_number: int,
        state: IssueState,
        actor: str = "system",
        force: bool = False,
    ) -> str:
        self.confirm_calls.append((issue_number, state, actor, force))
        return super().confirm_issue_state(issue_number, state, actor, force)


BLOCKED_BODY_TEMPLATE = (
    "<!-- vibe3-flow-state-start -->\n\n"
    "**Vibe3 Flow State**\n\n"
    "- **State**: blocked\n"
    "{reason_line}"
    "{deps_line}\n\n"
    "<!-- vibe3-flow-state-end -->"
)


def _blocked_body(reason: str | None = None, deps: list[int] | None = None) -> str:
    reason_line = f"- **Blocked reason**: {reason}\n" if reason else ""
    deps_line = (
        f"- **Blocked by**: {', '.join(f'#{d}' for d in deps)}\n" if deps else ""
    )
    return BLOCKED_BODY_TEMPLATE.format(reason_line=reason_line, deps_line=deps_line)


def _make_service(
    store: SQLiteClient,
    github: StubGitHubClient | MagicMock,
    label_service: StubLabelService | None = None,
) -> BlockedStateService:
    return BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service or StubLabelService(),
    )


def _patch_deps_resolved(resolved_map: dict[int, bool]) -> MagicMock:
    """Patch DependencyResolutionService.is_dependency_resolved."""

    def _factory(dep, **_kwargs):
        return DependencyResolution(
            resolved=resolved_map.get(dep, False),
            issue_number=dep,
            github_state="CLOSED" if resolved_map.get(dep, False) else "OPEN",
        )

    return _factory


# ============================================================================
# set_block + sync_block_state (alignment, no resume)
# ============================================================================


def test_set_block_writes_all_three_sources(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient()
    label_service = StubLabelService()

    service = _make_service(store, github, label_service)
    service.set_block(
        issue_number=123,
        branch="test-branch",
        reason=None,
        tasks=[456],
        actor="executor/agent",
    )

    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_by_issue") == 456
    assert label_service.current_state == IssueState.BLOCKED


def test_sync_block_state_aligns_cache_to_body_truth(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test", flow_status="active")
    github = StubGitHubClient(issue_body=_blocked_body(reason="Remote truth"))
    label_service = StubLabelService()

    service = _make_service(store, github, label_service)
    service.sync_block_state(123, "test-branch")

    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") == "Remote truth"


def test_sync_block_state_no_op_when_truth_not_blocked(tmp_path: Path) -> None:
    """sync_block_state must NOT resume or infer target when truth is active."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        plan_ref="plan.md",
        report_ref="report.md",
    )
    github = StubGitHubClient(issue_body="")  # no blocked projection
    label_service = TrackingLabelService()
    label_service.current_state = IssueState.REVIEW

    service = _make_service(store, github, label_service)
    service.sync_block_state(123, "test-branch")

    # No label transition, no target inference
    assert label_service.confirm_calls == []


def test_sync_block_state_restores_missing_blocked_label(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "task/issue-100",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="some reason",
    )
    github = StubGitHubClient(issue_body=_blocked_body(reason="some reason"))
    label_service = TrackingLabelService()

    service = _make_service(store, github, label_service)
    service.sync_block_state(100, "task/issue-100")

    assert len(label_service.confirm_calls) > 0
    assert label_service.confirm_calls[-1][1] == IssueState.BLOCKED


def test_sync_block_state_preserves_human_reason(tmp_path: Path) -> None:
    """sync_block_state must never clear a human blocked_reason."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(issue_body=_blocked_body(reason="Human gate"))
    label_service = StubLabelService()

    service = _make_service(store, github, label_service)
    service.sync_block_state(123, "test-branch")

    # Reason preserved in DB cache
    assert store.get_flow_state("test-branch").get("blocked_reason") == "Human gate"
    # Reason preserved in body (not cleared)
    assert "Human gate" in github.get_issue_body(123)


# ============================================================================
# evaluate_auto_eligibility (read-only, snapshot-bound)
# ============================================================================


def test_evaluate_not_eligible_when_human_reason_present(tmp_path: Path) -> None:
    """Truth table row 1+2: reason present -> NOT_ELIGIBLE regardless of deps."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(issue_body=_blocked_body(reason="Human gate", deps=[456]))

    service = _make_service(store, github)
    decision = service.evaluate_auto_eligibility(123, "test-branch")

    assert decision.verdict == AutoResumeVerdict.NOT_ELIGIBLE
    assert decision.reason_code == AutoResumeReasonCode.HUMAN_REASON_PRESENT


def test_evaluate_not_eligible_when_dependency_open(tmp_path: Path) -> None:
    """Truth table row 3: reason absent but dep open -> NOT_ELIGIBLE."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(issue_body=_blocked_body(deps=[456]))

    service = _make_service(store, github)
    with patch(
        "vibe3.services.shared.dependency_resolution.DependencyResolutionService.is_dependency_resolved",
        side_effect=_patch_deps_resolved({456: False}),
    ):
        decision = service.evaluate_auto_eligibility(123, "test-branch")

    assert decision.verdict == AutoResumeVerdict.NOT_ELIGIBLE
    assert decision.reason_code == AutoResumeReasonCode.DEPENDENCY_OPEN


def test_evaluate_not_eligible_when_truth_unreadable(tmp_path: Path) -> None:
    """Truth table row 4: GitHub unreadable -> NOT_ELIGIBLE (fail closed)."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = MagicMock()
    github.get_issue_snapshot.side_effect = Exception("GitHub API unavailable")

    service = _make_service(store, github)
    decision = service.evaluate_auto_eligibility(123, "test-branch")

    assert decision.verdict == AutoResumeVerdict.NOT_ELIGIBLE
    assert decision.reason_code == AutoResumeReasonCode.TRUTH_UNREADABLE


def test_evaluate_eligible_when_reason_absent_and_all_deps_closed(
    tmp_path: Path,
) -> None:
    """Truth table row 5+6: reason absent + all deps closed -> ELIGIBLE."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(
        issue_body=_blocked_body(deps=[456, 789]),
        updated_at="2026-07-02T12:00:00Z",
    )

    service = _make_service(store, github)
    with patch(
        "vibe3.services.shared.dependency_resolution.DependencyResolutionService.is_dependency_resolved",
        side_effect=_patch_deps_resolved({456: True, 789: True}),
    ):
        decision = service.evaluate_auto_eligibility(123, "test-branch")

    assert decision.verdict == AutoResumeVerdict.ELIGIBLE
    assert decision.truth_snapshot == "2026-07-02T12:00:00Z"
    assert sorted(decision.closed_deps) == [456, 789]


# ============================================================================
# apply_auto_resume (existing flow -> handoff, pre-flow -> ready)
# ============================================================================


def test_apply_auto_resume_existing_flow_targets_handoff(tmp_path: Path) -> None:
    """Truth table row 5: existing flow + eligible -> handoff."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test", plan_ref="plan.md")
    github = StubGitHubClient(issue_body=_blocked_body(deps=[]), updated_at="ts-1")
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = _make_service(store, github, label_service)
    decision = service.evaluate_auto_eligibility(123, "test-branch")
    result = service.apply_auto_resume(decision)

    assert result.success
    assert result.target_state == IssueState.HANDOFF
    assert label_service.current_state == IssueState.HANDOFF


def test_apply_auto_resume_pre_flow_targets_ready(tmp_path: Path) -> None:
    """Truth table row 6: pre-flow (no scene) + eligible -> ready."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    github = StubGitHubClient(issue_body=_blocked_body(deps=[]), updated_at="ts-1")
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = _make_service(store, github, label_service)
    decision = service.evaluate_auto_eligibility(123, "")
    result = service.apply_auto_resume(decision)

    assert result.success
    assert result.target_state == IssueState.READY


def test_apply_auto_resume_rejects_stale_decision(tmp_path: Path) -> None:
    """Race test: truth changed between evaluate and apply -> reject (zero mutation)."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(
        issue_body=_blocked_body(deps=[]), updated_at="ts-original"
    )
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = _make_service(store, github, label_service)
    decision = service.evaluate_auto_eligibility(123, "test-branch")
    assert decision.truth_snapshot == "ts-original"

    # Simulate truth changing between evaluate and apply
    github._updated_at = "ts-changed"

    result = service.apply_auto_resume(decision)
    assert not result.success
    # Zero mutation: label unchanged, body unchanged
    assert label_service.current_state == IssueState.BLOCKED


def test_apply_auto_resume_rejects_non_eligible_decision(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    service = _make_service(store, StubGitHubClient())

    bad_decision = AutoResumeDecision(
        verdict=AutoResumeVerdict.NOT_ELIGIBLE,
        reason_code=AutoResumeReasonCode.HUMAN_REASON_PRESENT,
        issue_number=1,
        branch="b",
        truth_snapshot=None,
    )
    result = service.apply_auto_resume(bad_decision)
    assert not result.success


# ============================================================================
# manual_resume (authorized clear + explicit/inferred target)
# ============================================================================


def test_manual_resume_clears_reason_and_advances(tmp_path: Path) -> None:
    """Truth table row 7: reason present + deps closed + manual -> clear + advance."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test", plan_ref="plan.md")
    github = StubGitHubClient(issue_body=_blocked_body(reason="Human gate"))
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = _make_service(store, github, label_service)
    result = service.manual_resume(
        issue_number=123,
        branch="test-branch",
        actor="human:resume",
        reason="Resolved manually",
    )

    assert result.success
    # Reason cleared in body
    assert "Human gate" not in (github.get_issue_body(123) or "")


def test_manual_resume_fail_closed_on_open_dep(tmp_path: Path) -> None:
    """Truth table row 8: open dep + manual no force -> remain blocked."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(issue_body=_blocked_body(reason=None, deps=[456]))
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = _make_service(store, github, label_service)
    with patch(
        "vibe3.services.shared.dependency_resolution.DependencyResolutionService.is_dependency_resolved",
        side_effect=_patch_deps_resolved({456: False}),
    ):
        with pytest.raises(UserError, match="open dependencies"):
            service.manual_resume(
                issue_number=123,
                branch="test-branch",
                actor="human:resume",
                reason="try resume",
            )

    # Zero mutation
    assert label_service.current_state == IssueState.BLOCKED


def test_manual_resume_force_overrides_open_dep(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(issue_body=_blocked_body(reason="gate", deps=[456]))
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = _make_service(store, github, label_service)
    with patch(
        "vibe3.services.shared.dependency_resolution.DependencyResolutionService.is_dependency_resolved",
        side_effect=_patch_deps_resolved({456: False}),
    ):
        result = service.manual_resume(
            issue_number=123,
            branch="test-branch",
            actor="human:resume",
            reason="forced",
            force=True,
        )

    assert result.success


def test_manual_resume_fail_closed_on_unreadable_truth(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = MagicMock()
    github.get_issue_body.side_effect = Exception("GitHub down")

    service = _make_service(store, github)
    with pytest.raises(UserError, match="unreadable"):
        service.manual_resume(
            issue_number=123,
            branch="test-branch",
            actor="human:resume",
            reason="try",
        )


# ============================================================================
# #3184 Regression: durable human reason survives all auto paths
# ============================================================================


def test_3184_durable_reason_survives_auto_evaluate(tmp_path: Path) -> None:
    """A no-op block with a durable human reason must survive auto eligibility."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test", plan_ref="plan.md")
    github = StubGitHubClient(issue_body=_blocked_body(reason="Awaiting human review"))

    service = _make_service(store, github)
    decision = service.evaluate_auto_eligibility(123, "test-branch")

    assert decision.verdict == AutoResumeVerdict.NOT_ELIGIBLE
    assert decision.reason_code == AutoResumeReasonCode.HUMAN_REASON_PRESENT
    # Zero mutation: reason survives
    assert "Awaiting human review" in github.get_issue_body(123)


def test_3184_auto_path_has_no_callable_api_to_clear_reason(tmp_path: Path) -> None:
    """No auto-path method (sync_block_state / evaluate / apply) clears reason."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")
    github = StubGitHubClient(issue_body=_blocked_body(reason="Human gate", deps=[456]))
    label_service = StubLabelService()
    label_service.current_state = IssueState.BLOCKED

    service = _make_service(store, github, label_service)

    # sync_block_state: preserves reason
    service.sync_block_state(123, "test-branch")
    assert "Human gate" in github.get_issue_body(123)

    # evaluate_auto_eligibility: read-only
    with patch(
        "vibe3.services.shared.dependency_resolution.DependencyResolutionService.is_dependency_resolved",
        side_effect=_patch_deps_resolved({456: True}),
    ):
        decision = service.evaluate_auto_eligibility(123, "test-branch")
    # Human reason -> NOT_ELIGIBLE even though deps closed
    assert decision.verdict == AutoResumeVerdict.NOT_ELIGIBLE
    assert "Human gate" in github.get_issue_body(123)

    # apply_auto_resume on NOT_ELIGIBLE decision: zero mutation
    result = service.apply_auto_resume(decision)
    assert not result.success
    assert "Human gate" in github.get_issue_body(123)


# ============================================================================
# Query / consistency operations (unchanged behavior)
# ============================================================================


def test_validate_consistency_detects_mismatch(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="DB says blocked",
    )
    github = StubGitHubClient(
        issue_body=(
            "<!-- vibe3-flow-state-start -->\n\n"
            "**Vibe3 Flow State**\n\n"
            "- **State**: active\n\n"
            "<!-- vibe3-flow-state-end -->"
        )
    )
    service = _make_service(store, github)

    report = service.validate_consistency("test-branch", 123)
    assert not report.is_consistent
    assert report.database_state.is_blocked
    assert not report.body_state.is_blocked


def test_resolve_truth_reads_from_issue_body_first(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test", flow_status="active")
    github = StubGitHubClient(issue_body=_blocked_body(reason="Body truth"))

    service = _make_service(store, github)
    state = service.resolve_truth("test-branch", 123)
    assert state.is_blocked
    assert state.blocked_reason == "Body truth"


def test_resolve_truth_fallback_to_database_on_github_failure(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state(
        "test-branch",
        flow_slug="test",
        flow_status="blocked",
        blocked_reason="DB cache truth",
    )
    github = MagicMock()
    github.get_issue_body.side_effect = Exception("GitHub API error")

    service = _make_service(store, github)
    state = service.resolve_truth("test-branch", 123)
    assert state.is_blocked
    assert state.blocked_reason == "DB cache truth"
