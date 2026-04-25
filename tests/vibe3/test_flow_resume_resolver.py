"""Tests for flow resume resolver."""

from datetime import datetime

from vibe3.models.flow import FlowState
from vibe3.models.orchestration import IssueState
from vibe3.models.verdict import VerdictRecord
from vibe3.services.flow_resume_resolver import infer_resume_label


def _create_verdict(verdict: str) -> VerdictRecord:
    return VerdictRecord(
        verdict=verdict,  # type: ignore[arg-type]
        actor="system",
        role="reviewer",
        timestamp=datetime.now(),
        flow_branch="task/issue-1",
    )


def test_infer_resume_label_with_pr() -> None:
    """PR exists -> HANDOFF."""
    state = FlowState(branch="task/issue-1", flow_slug="test", pr_ref="http://pr/1")
    assert infer_resume_label(state) == IssueState.HANDOFF


def test_infer_resume_label_audit_pass() -> None:
    """Audit pass -> IN_PROGRESS."""
    state = FlowState(
        branch="task/issue-1",
        flow_slug="test",
        audit_ref="audit.md",
        latest_verdict=_create_verdict("PASS"),
    )
    assert infer_resume_label(state) == IssueState.IN_PROGRESS


def test_infer_resume_label_audit_unknown() -> None:
    """Audit unknown -> HANDOFF."""
    state = FlowState(
        branch="task/issue-1",
        flow_slug="test",
        audit_ref="audit.md",
        latest_verdict=_create_verdict("UNKNOWN"),
    )
    assert infer_resume_label(state) == IssueState.HANDOFF


def test_infer_resume_label_plan_and_report() -> None:
    """Plan and report exist but no audit -> REVIEW."""
    state = FlowState(
        branch="task/issue-1",
        flow_slug="test",
        plan_ref="plan.md",
        report_ref="report.md",
    )
    assert infer_resume_label(state) == IssueState.REVIEW


def test_infer_resume_label_plan_only() -> None:
    """Only plan exists -> IN_PROGRESS."""
    state = FlowState(
        branch="task/issue-1",
        flow_slug="test",
        plan_ref="plan.md",
    )
    assert infer_resume_label(state) == IssueState.IN_PROGRESS


def test_infer_resume_label_empty() -> None:
    """Nothing exists -> CLAIMED."""
    state = FlowState(
        branch="task/issue-1",
        flow_slug="test",
    )
    assert infer_resume_label(state) == IssueState.CLAIMED
