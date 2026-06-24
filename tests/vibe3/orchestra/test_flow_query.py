"""Tests for FlowManager query operations."""

from unittest.mock import MagicMock, patch
import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.flow_dispatch import FlowManager


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

    @pytest.mark.slow
    def test_get_pr_for_issue_returns_none_without_flow(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(manager, "get_flow_for_issue", return_value=None):
            with patch.object(manager.github, "list_prs_for_branch", return_value=[]):
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

    def test_create_flow_for_issue_delegates_bootstrap_to_shared_service(self):
        config = OrchestraConfig(max_concurrent_flows=5)
        registry = MagicMock()
        manager = FlowManager(config, registry=registry)
        issue = make_issue(320, "Bootstrap shared")

        with patch.object(
            registry,
            "count_live_worker_sessions",
            return_value=0,
        ):
            with patch.object(
                manager._bootstrap_service,
                "bootstrap_issue_flow",
                return_value={"branch": "task/issue-320"},
            ) as mock_bootstrap:
                with patch.object(manager.store, "get_flows_by_issue", return_value=[]):
                    with patch.object(
                        manager.store, "get_flow_state", return_value=None
                    ):
                        result = manager.create_flow_for_issue(issue)

        mock_bootstrap.assert_called_once()
        assert result == {"branch": "task/issue-320"}

    def test_create_flow_for_issue_delegates_stale_rebuild_to_shared_service(
        self,
    ):
        config = OrchestraConfig(max_concurrent_flows=5)
        manager = FlowManager(config, registry=MagicMock())
        issue = make_issue(320, "Rebuild me")

        with patch.object(
            manager._bootstrap_service,
            "rebuild_stale_issue_flow",
            return_value={"branch": "task/issue-320"},
        ) as mock_rebuild:
            with patch.object(
                manager.store,
                "get_flows_by_issue",
                return_value=[{"branch": "task/issue-320", "flow_status": "stale"}],
            ):
                result = manager.create_flow_for_issue(issue)

        mock_rebuild.assert_called_once_with(
            issue, branch="task/issue-320", slug="issue-320", ensure_worktree=True
        )
        assert result == {"branch": "task/issue-320"}
