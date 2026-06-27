"""Tests for flow classifier service."""

from vibe3.models.flow import FlowStatusResponse
from vibe3.services.flow.classifier import FlowState, get_flow_state


class TestGetFlowState:
    """Tests for get_flow_state() which maps flow_status to FlowState enum."""

    def test_review_status_maps_to_review_state(self):
        """flow_status='review' should map to FlowState.REVIEW."""
        flow = FlowStatusResponse(
            branch="task/issue-review",
            flow_slug="issue-review",
            flow_status="review",
        )
        assert get_flow_state(flow) == FlowState.REVIEW

    def test_failed_status_maps_to_failed_state(self):
        """flow_status='failed' should map to FlowState.FAILED."""
        flow = FlowStatusResponse(
            branch="task/issue-fail",
            flow_slug="issue-fail",
            flow_status="failed",
        )
        assert get_flow_state(flow) == FlowState.FAILED

    def test_existing_status_mappings_unchanged(self):
        """Existing status mappings should remain correct."""
        assert get_flow_state(
            FlowStatusResponse(
                branch="t/active", flow_slug="s-active", flow_status="active"
            )
        ) == FlowState.ACTIVE
        assert get_flow_state(
            FlowStatusResponse(
                branch="t/done", flow_slug="s-done", flow_status="done"
            )
        ) == FlowState.DONE
        assert get_flow_state(
            FlowStatusResponse(
                branch="t/stale", flow_slug="s-stale", flow_status="stale"
            )
        ) == FlowState.STALE
        assert get_flow_state(
            FlowStatusResponse(
                branch="t/aborted", flow_slug="s-aborted", flow_status="aborted"
            )
        ) == FlowState.ABORTED

    def test_blocked_inferred_from_blocked_reason(self):
        """Blocked status should be inferred from blocked_reason, not flow_status."""
        flow = FlowStatusResponse(
            branch="t/blocked", flow_slug="s-blocked", flow_status="active",
            blocked_reason="waiting for review",
        )
        assert get_flow_state(flow) == FlowState.BLOCKED