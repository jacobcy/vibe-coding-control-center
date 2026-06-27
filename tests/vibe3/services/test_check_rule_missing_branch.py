"""Tests for rule_missing_branch_cleanup terminal-state preservation.

Issue #3189: PR-backed terminal states (review/failed) must not be overwritten
to aborted when their local branch is deleted (normal post-PR housekeeping).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from vibe3.services.check.rule_checks import CheckContext, rule_missing_branch_cleanup


def _make_ctx(flow_status: str) -> CheckContext:
    return CheckContext(
        branch="task/issue-3189",
        flow_data={"flow_status": flow_status},
        flow_status=flow_status,
        is_active_flow=True,
        task_issue=3189,
        task_issue_closed=False,
        orchestration_state=None,
        issue_payload=None,
        issue_labels=[],
        issue_labels_loaded=True,
        branch_missing=True,
    )


def _make_svc() -> SimpleNamespace:
    return SimpleNamespace(
        _sync_rules=SimpleNamespace(
            local=SimpleNamespace(missing_branch_cleanup=SimpleNamespace(enabled=True))
        ),
        _flow_status_service=MagicMock(),
    )


def test_failed_flow_not_aborted_on_missing_branch() -> None:
    ctx = _make_ctx("failed")
    svc = _make_svc()
    result = rule_missing_branch_cleanup(ctx, svc)
    assert result is None
    svc._flow_status_service.mark_flow_aborted.assert_not_called()


def test_review_flow_not_aborted_on_missing_branch() -> None:
    ctx = _make_ctx("review")
    svc = _make_svc()
    result = rule_missing_branch_cleanup(ctx, svc)
    assert result is None
    svc._flow_status_service.mark_flow_aborted.assert_not_called()


def test_aborted_flow_not_re_aborted_on_missing_branch() -> None:
    ctx = _make_ctx("aborted")
    svc = _make_svc()
    result = rule_missing_branch_cleanup(ctx, svc)
    assert result is None
    svc._flow_status_service.mark_flow_aborted.assert_not_called()


def test_done_flow_not_aborted_on_missing_branch() -> None:
    ctx = _make_ctx("done")
    svc = _make_svc()
    result = rule_missing_branch_cleanup(ctx, svc)
    assert result is None
    svc._flow_status_service.mark_flow_aborted.assert_not_called()


def test_active_flow_still_aborted_on_missing_branch() -> None:
    ctx = _make_ctx("active")
    svc = _make_svc()
    result = rule_missing_branch_cleanup(ctx, svc)
    assert result is not None
    assert result.is_valid is False
    svc._flow_status_service.mark_flow_aborted.assert_called_once()
