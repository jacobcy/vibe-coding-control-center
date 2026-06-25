"""Tests for FlowOrchestratorService branch validation and baseline snapshot."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueInfo
from vibe3.services.orchestra.orchestrator import FlowOrchestratorService


def test_validate_or_recreate_branch_returns_true_when_verified() -> None:
    """Branch already based on scene_base_ref should be left untouched."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.get_merge_base.side_effect = ["same_sha", "same_sha"]
    service = FlowOrchestratorService(config, store=store, git=git, github=github)

    result = service._validate_or_recreate_branch("task/issue-123", issue_number=123)

    assert result is True
    git.delete_branch.assert_not_called()
    git.create_branch_ref.assert_not_called()


def test_validate_or_recreate_branch_returns_false_when_diverged_reactivate() -> None:
    """Diverged branch kept as-is for reactivation has unknown creation source."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.get_merge_base.side_effect = ["sha_a", "sha_b"]
    service = FlowOrchestratorService(config, store=store, git=git, github=github)

    result = service._validate_or_recreate_branch(
        "task/issue-123", issue_number=123, reactivate_existing=True
    )

    assert result is False
    git.delete_branch.assert_not_called()
    git.create_branch_ref.assert_not_called()


def test_validate_or_recreate_branch_force_recreates_when_diverged() -> None:
    """Diverged branch without reactivation is force-recreated from scene_base_ref."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.get_merge_base.side_effect = ["sha_a", "sha_b"]
    service = FlowOrchestratorService(config, store=store, git=git, github=github)

    result = service._validate_or_recreate_branch(
        "task/issue-123", issue_number=123, reactivate_existing=False
    )

    assert result is True
    git.delete_branch.assert_called_once_with("task/issue-123", force=True)
    git.create_branch_ref.assert_called_once_with(
        "task/issue-123", start_ref=config.scene_base_ref
    )


@pytest.mark.slow
def test_bootstrap_issue_flow_omits_creation_source_when_diverged_kept() -> None:
    """creation_source stays None when an existing diverged branch is kept as-is."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = True
    git.get_merge_base.side_effect = ["sha_a", "sha_b"]
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = None
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "task/issue-555"})
    )

    service.bootstrap_issue_flow(
        IssueInfo(number=555, title="Diverged branch test"),
        branch="task/issue-555",
        source="skill",
        reactivate_existing=True,
    )

    _, kwargs = service.flow_service.create_flow.call_args
    assert kwargs["creation_source"] is None


@pytest.mark.slow
def test_bootstrap_issue_flow_sets_creation_source_for_new_branch() -> None:
    """A freshly created branch should record scene_base_ref as creation_source."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = False
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = None
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "task/issue-556"})
    )

    service.bootstrap_issue_flow(
        IssueInfo(number=556, title="New branch test"),
        branch="task/issue-556",
        source="skill",
    )

    _, kwargs = service.flow_service.create_flow.call_args
    assert kwargs["creation_source"] == config.scene_base_ref


def test_bootstrap_issue_flow_skip_git_omits_creation_source() -> None:
    """skip_git intake placeholders must not record a creation_source."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    store.get_flow_state.return_value = None
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "task/issue-557"})
    )

    service.bootstrap_issue_flow(
        IssueInfo(number=557, title="Intake placeholder"),
        branch="task/issue-557",
        source="skill",
        skip_git=True,
    )

    _, kwargs = service.flow_service.create_flow.call_args
    assert kwargs["creation_source"] is None
    git.branch_exists.assert_not_called()


def test_bootstrap_issue_flow_skips_baseline_without_worktree() -> None:
    """Bootstrap without worktree skips baseline creation (auto-degrade).

    Rationale: when ensure_worktree=False, process cwd is unreliable for
    snapshot context. Users who skip worktree should manage baseline
    themselves via `git checkout -b` + manual snapshot commands.
    """
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = False
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = None
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "task/issue-901"})
    )

    with patch(
        "vibe3.analysis.snapshot_service.save_branch_baseline"
    ) as mock_save_baseline:
        service.bootstrap_issue_flow(
            IssueInfo(number=901, title="Default baseline"),
            branch="task/issue-901",
            source="skill",
            ensure_worktree=False,
        )

    mock_save_baseline.assert_not_called()


def test_bootstrap_issue_flow_force_baseline_with_worktree() -> None:
    """force_baseline controls overwrite semantics when worktree is established."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = False
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = None
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "task/issue-902"})
    )

    with (
        patch("vibe3.services.orchestra.orchestrator.WorktreeManager") as mock_wt_cls,
        patch(
            "vibe3.analysis.snapshot_service.save_branch_baseline"
        ) as mock_save_baseline,
    ):
        mock_wt_ctx = MagicMock()
        mock_wt_ctx.path = "/tmp/worktree-902"
        mock_wt_cls.return_value.resolve_bootstrap_worktree_context.return_value = (
            mock_wt_ctx
        )

        service.bootstrap_issue_flow(
            IssueInfo(number=902, title="Force baseline"),
            branch="task/issue-902",
            source="flow:rebuild",
            ensure_worktree=True,
            force_baseline=True,
        )

    mock_save_baseline.assert_called_once_with(
        "task/issue-902", force=True, repo_path="/tmp/worktree-902"
    )
