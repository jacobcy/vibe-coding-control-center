"""Tests for FlowOrchestratorService."""

from unittest.mock import MagicMock, patch

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueInfo
from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
from vibe3.services.orchestra_status_service import OrchestraSnapshot


def test_flow_orchestrator_service_initialization() -> None:
    """FlowOrchestratorService should initialize with config."""
    config = load_orchestra_config()
    service = FlowOrchestratorService(config)

    assert service.config == config


def test_flow_orchestrator_can_snapshot() -> None:
    """FlowOrchestratorService should provide snapshot capability."""
    config = load_orchestra_config()
    service = FlowOrchestratorService(config)

    # Mock the HTTP server response via fetch_live_snapshot
    mock_snapshot = OrchestraSnapshot(
        timestamp=1234567890.0,
        server_running=True,
        active_issues=(),
        active_flows=0,
        active_worktrees=0,
    )

    with patch(
        "vibe3.services.flow_orchestrator_service.OrchestraStatusService.fetch_live_snapshot",
        return_value=mock_snapshot,
    ):
        snapshot = service.snapshot()

        assert snapshot is not None
        assert snapshot.server_running is True


def test_flow_orchestrator_snapshot_returns_none_when_unreachable() -> None:
    """FlowOrchestratorService.snapshot() returns None when server unreachable."""
    config = load_orchestra_config()
    service = FlowOrchestratorService(config)

    with patch(
        "vibe3.services.flow_orchestrator_service.OrchestraStatusService.fetch_live_snapshot",
        return_value=None,
    ):
        snapshot = service.snapshot()

        assert snapshot is None


def test_bootstrap_issue_flow_links_task_and_related_issues() -> None:
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = True
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = {
        "branch": "dev/issue-501",
        "flow_slug": "issue-501",
    }
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "dev/issue-501"})
    )
    service.task_service.link_issue = MagicMock()
    service.flow_service.block_flow = MagicMock()

    result = service.bootstrap_issue_flow(
        IssueInfo(number=501, title="Bootstrap me"),
        branch="dev/issue-501",
        source="skill",
        related_issue_numbers=(601,),
        dependency_issue_numbers=(701,),
    )

    service.task_service.link_issue.assert_any_call(
        "dev/issue-501", 501, "task", actor=None
    )
    service.task_service.link_issue.assert_any_call(
        "dev/issue-501", 601, "related", actor=None
    )
    service.flow_service.block_flow.assert_called_once_with(
        "dev/issue-501",
        blocked_by_issue=701,
        actor=None,
    )
    assert result["branch"] == "dev/issue-501"


def test_create_flow_for_issue_uses_shared_bootstrap_interface() -> None:
    config = load_orchestra_config()
    service = FlowOrchestratorService(config)
    issue = IssueInfo(number=777, title="Shared bootstrap")

    with patch.object(
        service, "bootstrap_issue_flow", return_value={"branch": "task/issue-777"}
    ) as mock_bootstrap:
        with patch.object(service.store, "get_flows_by_issue", return_value=[]):
            with patch.object(service.store, "get_flow_state", return_value=None):
                result = service.create_flow_for_issue(issue)

    mock_bootstrap.assert_called_once()
    assert result == {"branch": "task/issue-777"}
