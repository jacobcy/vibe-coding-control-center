"""Tests for the audit blocked flows helper script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    script_path = Path("scripts/audit-blocked-flows.py")
    spec = importlib.util.spec_from_file_location(
        "audit_blocked_flows_script", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_affected_issue_numbers_from_markdown_section() -> None:
    module = _load_module()

    body = """
## Summary
Something

## Affected Issues
- #2952
- #2953

## Evidence Chain
- obs-20260626T120000-aaaaaaaa
"""

    assert module.extract_affected_issue_numbers(body) == {2952, 2953}


def test_screen_flow_skips_when_open_decision_already_covers_issue() -> None:
    module = _load_module()

    flow = module.BlockedFlow(
        branch="task/issue-2953",
        issue_number=2953,
        flow_status="blocked",
        has_worktree=True,
        has_plan_ref=True,
        has_report_ref=True,
        evidence_count=2,
        execution_age_days=0,
    )

    screened = module.screen_flow(
        flow,
        covered_issue_numbers={2953},
    )

    assert screened.screening_verdict == "covered_by_open_decision"


def test_screen_flow_keeps_candidate_for_agent_judgment() -> None:
    module = _load_module()

    flow = module.BlockedFlow(
        branch="task/issue-3001",
        issue_number=3001,
        flow_status="aborted",
        blocked_reason="deferred until next quarter",
        evidence_count=1,
        execution_age_days=25,
    )

    screened = module.screen_flow(
        flow,
        observed_issues=set(),
        covered_issue_numbers=set(),
    )

    assert screened.screening_verdict == "candidate"
    assert screened.evidence_count == 1
    assert screened.execution_age_days is not None


def test_flow_to_dict_uses_shared_fact_shape() -> None:
    module = _load_module()

    flow = module.BlockedFlow(
        branch="task/issue-3002",
        issue_number=3002,
        flow_status="blocked",
        signal_tags=["has_block_events"],
        reason_pattern_hits=["state unchanged"],
        event_types=["flow_blocked"],
        block_evidence=["block_event_detail: state unchanged"],
        evidence_count=3,
        has_worktree=True,
        execution_age_days=2,
        issue_state="OPEN",
        has_merged_pr=False,
        pr_number=4001,
        last_event_detail="state unchanged",
        last_event_time="2026-06-26T00:00:00Z",
    )

    data = module.flow_to_dict(flow)

    assert data["branch"] == "task/issue-3002"
    assert data["issue_number"] == 3002
    assert data["signal_tags"] == ["has_block_events"]
    assert data["reason_pattern_hits"] == ["state unchanged"]
    assert data["event_types"] == ["flow_blocked"]
    assert data["issue_state"] == "OPEN"
    assert data["pr_number"] == 4001


def test_format_event_line_emits_plain_fact_row() -> None:
    module = _load_module()

    line = module.format_event_line(
        {
            "created_at": "2026-06-26T12:34:56Z",
            "event_type": "flow_blocked",
            "detail": "state unchanged after review",
        }
    )

    assert "2026-06-26 12:34:56" in line
    assert "flow_blocked" in line
    assert "state unchanged after review" in line


def test_script_no_longer_exposes_dependency_tracing_mode() -> None:
    source = Path("scripts/audit-blocked-flows.py").read_text(encoding="utf-8")

    assert "--trace-deps" not in source
    assert "trace_dependency_chain" not in source
