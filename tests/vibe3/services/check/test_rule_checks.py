"""Tests for check rule_checks cleanup rules."""

from unittest.mock import MagicMock

from vibe3.models import IssueState
from vibe3.services.check.rule_checks import (
    CheckContext,
    rule_empty_ready_cleanup,
    rule_orphaned_flow_cleanup,
)


def _make_context(**kwargs):
    """Helper to create CheckContext with defaults."""
    defaults = {
        "branch": "task/issue-1",
        "flow_data": {},
        "flow_status": "active",
        "is_active_flow": True,
        "task_issue": None,
        "task_issue_closed": False,
        "orchestration_state": None,
        "issue_payload": None,
        "issue_labels": [],
        "issue_labels_loaded": False,
        "branch_missing": False,
    }
    return CheckContext(**{**defaults, **kwargs})


def _make_service(**kwargs):
    """Helper to create mock service."""
    svc = MagicMock()
    svc._sync_rules = MagicMock()
    svc._sync_rules.local = MagicMock()
    svc._sync_rules.local.orphaned_flow_cleanup = MagicMock()
    svc._sync_rules.local.orphaned_flow_cleanup.enabled = kwargs.get(
        "orphaned_flow_cleanup_enabled", True
    )
    svc._sync_rules.local.empty_ready_cleanup = MagicMock()
    svc._sync_rules.local.empty_ready_cleanup.enabled = kwargs.get(
        "empty_ready_cleanup_enabled", True
    )
    svc._has_worktree = MagicMock(return_value=kwargs.get("has_worktree", False))
    return svc


def test_orphaned_flow_cleanup_skips_blocked_placeholder():
    """Orphaned flow cleanup should skip blocked placeholder flows."""
    ctx = _make_context(flow_status="blocked")
    svc = _make_service()
    result = rule_orphaned_flow_cleanup(ctx, svc)
    assert result is None  # Skipped


def test_empty_ready_cleanup_skips_blocked_placeholder():
    """Empty ready cleanup should skip blocked placeholder flows."""
    ctx = _make_context(
        flow_status="blocked",
        orchestration_state=IssueState.READY,
    )
    svc = _make_service()
    result = rule_empty_ready_cleanup(ctx, svc)
    assert result is None  # Skipped
