"""Tests for manager role service request preparation."""

from pathlib import Path
from unittest.mock import patch

from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.execution.role_services import build_manager_dispatch_request
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.READY,
        labels=["state/ready"],
    )


def make_config() -> OrchestraConfig:
    return OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid"))


class TestManagerRoleServicePreparation:
    """Manager dispatch should be reduced to request preparation only."""

    def test_prepare_dispatch_request_returns_none_when_flow_missing_branch(self):
        issue = make_issue()

        with patch(
            "vibe3.execution.role_services.FlowManager.create_flow_for_issue",
            return_value={"branch": ""},
        ):
            assert (
                build_manager_dispatch_request(
                    make_config(),
                    issue,
                    repo_path=Path("/tmp/repo"),
                )
                is None
            )

    def test_prepare_dispatch_request_builds_self_invocation(self):
        issue = make_issue(number=102, title="Manager real dispatch")

        with patch(
            "vibe3.execution.role_services.FlowManager.create_flow_for_issue",
            return_value={"branch": "task/issue-102"},
        ):
            request = build_manager_dispatch_request(
                make_config(),
                issue,
                repo_path=Path("/tmp/repo"),
            )

        assert request is not None
        assert request.role == "manager"
        assert request.target_id == 102
        assert request.target_branch == "task/issue-102"
        assert request.cwd is None
        assert request.repo_path == str(Path("/tmp/repo").resolve())
        assert request.mode == "async"
        assert request.worktree_requirement == WorktreeRequirement.PERMANENT
        assert request.cmd is not None
        assert request.cmd[-2:] == ["102", "--no-async"]
        assert "VIBE3_ASYNC_CHILD" in request.env
        assert request.refs["issue_title"] == "Manager real dispatch"
