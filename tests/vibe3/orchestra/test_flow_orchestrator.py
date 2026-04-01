"""Tests for Orchestra FlowManager."""

from unittest.mock import patch

from vibe3.manager.flow_manager import FlowManager
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestFlowManager:
    """Tests for FlowManager."""

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
            pr_number = manager.get_pr_for_issue(42)

        assert pr_number is None

    def test_create_flow_for_issue_delegates_to_git_client_create_branch_ref(self):
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=222, title="orchestra branch create")

        class _Flow:
            def model_dump(self):  # type: ignore[no-untyped-def]
                return {"branch": "task/issue-222", "flow_slug": "issue-222"}

        with patch.object(manager, "get_active_flow_count", return_value=0):
            with patch.object(manager.git, "branch_exists", return_value=False):
                with patch.object(
                    manager.git, "create_branch_ref", return_value=None
                ) as mock_create_ref:
                    with patch.object(
                        manager.flow_service,
                        "create_flow",
                        return_value=_Flow(),
                    ) as mock_create_flow:
                        with patch.object(
                            manager.task_service, "link_issue", return_value=None
                        ) as mock_link_issue:
                            flow = manager.create_flow_for_issue(issue)

        assert flow["branch"] == "task/issue-222"
        mock_create_ref.assert_called_once_with(
            "task/issue-222",
            start_ref="origin/main",
        )
        mock_create_flow.assert_called_once_with(
            slug="issue-222",
            branch="task/issue-222",
            actor=None,
            initiated_by="orchestra:dispatcher",
        )
        mock_link_issue.assert_called_once_with(
            "task/issue-222", 222, "task", actor=None
        )
