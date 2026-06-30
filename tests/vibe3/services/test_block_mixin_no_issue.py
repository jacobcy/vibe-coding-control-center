"""Tests that block_flow raises SystemError when no task issue is linked."""

from unittest.mock import patch

import pytest

from vibe3.exceptions import SystemError


def test_block_flow_raises_when_no_issue(temp_store):
    """block_flow with no linked task issue must raise SystemError, not write_cache."""
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow.block_mixin import FlowLifecycleMixin

    store: SQLiteClient = temp_store
    store.update_flow_state("task/issue-orphan", flow_slug="test", flow_status="active")

    class TestService(FlowLifecycleMixin):
        def __init__(self, store):
            self.store = store

    svc = TestService(store=store)

    with patch(
        "vibe3.services.issue.flow.IssueFlowService.resolve_task_issue_number",
        return_value=None,  # No linked issue
    ):
        with pytest.raises(SystemError):
            svc.block_flow(
                branch="task/issue-orphan",
                reason="test reason",
                blocked_by_issue=None,
            )
