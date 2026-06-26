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
    )

    screened = module.screen_flow(
        flow,
        {
            "has_worktree": True,
            "plan_ref": "@plan",
            "report_ref": "@report",
            "updated_at": "2026-06-26T00:00:00Z",
        },
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
    )

    screened = module.screen_flow(
        flow,
        {
            "has_worktree": False,
            "updated_at": "2026-06-01T00:00:00Z",
            "task_issue_number": 3001,
        },
        observed_issues=set(),
        covered_issue_numbers=set(),
    )

    assert screened.screening_verdict == "candidate"
    assert screened.evidence_count == 1
    assert screened.execution_age_days is not None
