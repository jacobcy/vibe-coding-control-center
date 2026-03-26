"""Tests for flow close target resolution."""

from unittest.mock import Mock

from vibe3.services.flow_service import FlowService


class TestFlowCloseTargetDecision:
    """Tests for flow close target resolution."""

    def test_done_returns_to_single_dependent_flow(self, mock_store: Mock) -> None:
        """Single active dependent flow should be the close target."""
        mock_store.get_flow_dependents.return_value = ["task/downstream-flow"]

        service = FlowService(store=mock_store)
        decision = service.resolve_close_target("task/current-flow")

        assert decision.target_branch == "task/downstream-flow"
        assert decision.should_pull is False
        assert "dependent" in decision.reason.lower()

    def test_done_falls_back_to_main_when_no_dependents(self, mock_store: Mock) -> None:
        """No dependents should fall back to main."""
        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)
        decision = service.resolve_close_target("task/current-flow")

        assert decision.target_branch == "main"
        assert decision.should_pull is True
        assert "safe branch" in decision.reason.lower()

    def test_done_warns_on_multiple_dependents_and_falls_back(
        self, mock_store: Mock
    ) -> None:
        """Multiple dependents should warn and fall back to main."""
        mock_store.get_flow_dependents.return_value = [
            "task/flow-a",
            "task/flow-b",
        ]

        service = FlowService(store=mock_store)
        decision = service.resolve_close_target("task/current-flow")

        assert decision.target_branch == "main"
        assert decision.should_pull is True

    def test_done_handles_dependent_query_failure(self, mock_store: Mock) -> None:
        """Dependent query failure should fall back to main safely."""
        mock_store.get_flow_dependents.side_effect = RuntimeError("db error")

        service = FlowService(store=mock_store)
        decision = service.resolve_close_target("task/current-flow")

        assert decision.target_branch == "main"
        assert decision.should_pull is True
