"""Tests for FlowManager query operations."""

from unittest.mock import patch

from vibe3.execution.flow_dispatch import FlowManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestFlowQuery:
    """Tests for FlowManager query operations."""

    def test_get_flow_for_issue(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(
            manager.store,
            "get_flows_by_issue",
            return_value=[{"branch": "task/test", "pr_number": 123}],
        ):
            flow = manager.get_flow_for_issue(42)

        assert flow is not None
        assert flow["branch"] == "task/test"

    def test_get_flow_for_issue_prefers_active_canonical_flow(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(
            manager.store,
            "get_flows_by_issue",
            return_value=[
                {"branch": "debug/vibe-server-fix", "flow_status": "done"},
                {"branch": "task/issue-467", "flow_status": "active"},
            ],
        ):
            flow = manager.get_flow_for_issue(467)

        assert flow is not None
        assert flow["branch"] == "task/issue-467"

    def test_get_flow_for_issue_returns_none(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(manager.store, "get_flows_by_issue", return_value=[]):
            flow = manager.get_flow_for_issue(42)

        assert flow is None

    def test_get_pr_for_issue_from_flow(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(
            manager,
            "get_flow_for_issue",
            return_value={"branch": "task/test", "pr_number": 789},
        ):
            pr_number = manager.get_pr_for_issue(42)

        assert pr_number == 789

    def test_get_pr_for_issue_returns_none_without_flow(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(manager, "get_flow_for_issue", return_value=None):
            with patch.object(manager.github, "get_pr_for_issue", return_value=None):
                pr_number = manager.get_pr_for_issue(42)

        assert pr_number is None

    def test_get_active_flow_count_only_counts_execution_states(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(
            manager.store,
            "get_all_flows",
            return_value=[
                {"branch": "task/issue-320", "flow_status": "active"},
                {"branch": "task/issue-356", "flow_status": "active"},
                {"branch": "task/issue-372", "flow_status": "active"},
                {"branch": "dev/issue-435", "flow_status": "active"},
            ],
        ):
            with patch.object(manager.store, "get_issue_links", return_value=[]):
                with patch.object(
                    manager.label_service,
                    "get_state",
                    side_effect=[
                        IssueState.READY,
                        IssueState.CLAIMED,
                        IssueState.BLOCKED,
                    ],
                ):
                    count = manager.get_active_flow_count()

        assert count == 1
