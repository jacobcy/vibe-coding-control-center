"""Regression tests for FlowOrchestratorService merge-base guard."""

from unittest.mock import MagicMock

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueInfo
from vibe3.services.orchestra.orchestrator import FlowOrchestratorService


def test_bootstrap_issue_flow_checkouts_recreated_branch_in_non_worktree_mode() -> None:
    """Non-worktree mode must checkout a polluted branch after recreation."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = True
    git.get_merge_base.side_effect = ["old-parent-sha", "origin-main-sha"]
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = {
        "branch": "dev/issue-997",
        "flow_slug": "issue-997",
    }
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "dev/issue-997"})
    )

    result = service.bootstrap_issue_flow(
        IssueInfo(number=997, title="Recreate checkout test"),
        branch="dev/issue-997",
        source="skill",
        ensure_worktree=False,
    )

    git.delete_branch.assert_called_once_with("dev/issue-997", force=True)
    git.create_branch_ref.assert_called_once_with(
        "dev/issue-997", start_ref=config.scene_base_ref
    )
    git.switch_branch.assert_called_once_with("dev/issue-997")
    assert result["branch"] == "dev/issue-997"
