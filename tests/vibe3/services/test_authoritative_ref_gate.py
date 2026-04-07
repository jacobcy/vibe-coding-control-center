"""Tests for authoritative ref gate service."""

from unittest.mock import MagicMock

from vibe3.services.authoritative_ref_gate import (
    has_authoritative_ref,
    require_authoritative_ref,
)


def test_has_authoritative_ref_reads_named_flow_attribute() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(plan_ref="docs/plans/42.md")

    result = has_authoritative_ref(
        flow_service=flow_service,
        branch="task/demo",
        ref_name="plan_ref",
    )

    assert result is True


def test_require_authoritative_ref_blocks_when_missing() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(report_ref=None)
    block_issue = MagicMock()

    result = require_authoritative_ref(
        flow_service=flow_service,
        branch="task/demo",
        ref_name="report_ref",
        issue_number=42,
        reason="missing report_ref",
        actor="agent:run",
        block_issue=block_issue,
    )

    assert result is False
    block_issue.assert_called_once_with(
        issue_number=42,
        reason="missing report_ref",
        actor="agent:run",
        repo=None,
    )


def test_require_authoritative_ref_can_fail_without_issue_side_effect() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(audit_ref=None)
    block_issue = MagicMock()

    result = require_authoritative_ref(
        flow_service=flow_service,
        branch="task/demo",
        ref_name="audit_ref",
        issue_number=None,
        reason="missing audit_ref",
        actor="agent:review",
        block_issue=block_issue,
    )

    assert result is False
    block_issue.assert_not_called()
