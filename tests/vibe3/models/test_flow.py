"""Tests for Flow model fields."""

from vibe3.models.flow import FlowState, FlowStatusResponse


class TestFlowBlockedReasonField:
    """Tests for blocked_reason field in Flow model."""

    def test_flow_state_blocked_reason_field(self):
        """Test FlowState model has blocked_reason field."""
        flow = FlowState(
            branch="test-branch",
            flow_slug="test-flow",
            blocked_reason="Dependency not ready",
        )
        assert flow.blocked_reason == "Dependency not ready"

    def test_flow_status_response_blocked_reason_field(self):
        """Test FlowStatusResponse model has blocked_reason field."""
        response = FlowStatusResponse(
            branch="test-branch",
            flow_slug="test-flow",
            flow_status="active",
            blocked_reason="Waiting for review",
        )
        assert response.blocked_reason == "Waiting for review"

    def test_flow_state_blocked_reason_optional(self):
        """Test that blocked_reason is optional."""
        flow = FlowState(branch="test-branch", flow_slug="test-flow")
        assert flow.blocked_reason is None

    def test_flow_status_response_blocked_reason_optional(self):
        """Test that blocked_reason is optional in FlowStatusResponse."""
        response = FlowStatusResponse(
            branch="test-branch", flow_slug="test-flow", flow_status="active"
        )
        assert response.blocked_reason is None
