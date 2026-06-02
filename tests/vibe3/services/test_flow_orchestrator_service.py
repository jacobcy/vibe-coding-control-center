"""Tests for FlowOrchestratorService."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueInfo
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
from vibe3.services.orchestra_status_service import OrchestraSnapshot


def _pr_response(
    *,
    number: int = 42,
    branch: str = "task/issue-123",
    state: PRState = PRState.OPEN,
    draft: bool = False,
) -> PRResponse:
    return PRResponse(
        number=number,
        title=f"PR {number}",
        body="",
        state=state,
        head_branch=branch,
        base_branch="main",
        url=f"https://example.com/pr/{number}",
        draft=draft,
        is_ready=not draft,
        ci_passed=False,
        ci_status=None,
        created_at=None,
        updated_at=None,
        merged_at=None,
        metadata=None,
    )


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


def test_bootstrap_issue_flow_checkouts_branch_in_non_worktree_mode() -> None:
    """CRITICAL: Non-worktree mode must checkout newly created branch.

    Without this, user stays on current branch while flow is on dev/issue-XXX,
    causing git history pollution (user commits on wrong branch).
    """
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = False
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = {
        "branch": "dev/issue-999",
        "flow_slug": "issue-999",
    }
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "dev/issue-999"})
    )

    # CRITICAL: ensure_worktree=False triggers checkout
    result = service.bootstrap_issue_flow(
        IssueInfo(number=999, title="Checkout test"),
        branch="dev/issue-999",
        source="skill",
        ensure_worktree=False,
    )

    # Verify fetch, create_branch, AND checkout were called
    git.fetch.assert_called_once_with("origin")
    git.create_branch_ref.assert_called_once_with(
        "dev/issue-999", start_ref=config.scene_base_ref
    )
    git.switch_branch.assert_called_once_with("dev/issue-999")
    assert result["branch"] == "dev/issue-999"


def test_bootstrap_issue_flow_skips_checkout_in_worktree_mode() -> None:
    """Worktree mode should NOT checkout branch (worktree handles isolation)."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = False
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = {
        "branch": "dev/issue-888",
        "flow_slug": "issue-888",
    }
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "dev/issue-888"})
    )

    # Mock worktree resolution
    with patch(
        "vibe3.services.flow_orchestrator_service.WorktreeManager"
    ) as worktree_cls:
        worktree = worktree_cls.return_value
        worktree.resolve_bootstrap_worktree_context.return_value = MagicMock(
            path="/tmp/repo/.worktrees/dev-issue-888"
        )

        result = service.bootstrap_issue_flow(
            IssueInfo(number=888, title="Worktree test"),
            branch="dev/issue-888",
            source="skill",
            ensure_worktree=True,  # Worktree mode
        )

    # Verify fetch and create_branch were called, but checkout was NOT
    git.fetch.assert_called_once_with("origin")
    git.create_branch_ref.assert_called_once_with(
        "dev/issue-888", start_ref=config.scene_base_ref
    )
    # CRITICAL: switch_branch should NOT be called in worktree mode
    git.switch_branch.assert_not_called()
    assert result["branch"] == "dev/issue-888"


def test_bootstrap_issue_flow_links_task_and_related_issues() -> None:
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = False
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

    # Verify fetch was called before branch creation
    git.fetch.assert_called_once_with("origin")
    git.create_branch_ref.assert_called_once_with(
        "dev/issue-501", start_ref=config.scene_base_ref
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


def test_bootstrap_persists_worktree_path() -> None:
    """bootstrap_issue_flow with ensure_worktree=True must persist worktree_path."""
    from vibe3.models.orchestration import IssueState

    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    git.branch_exists.return_value = False
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = {
        "branch": "task/issue-999",
        "flow_slug": "issue-999",
    }
    service = FlowOrchestratorService(config, store=store, git=git, github=github)
    service.flow_service.create_flow = MagicMock(
        return_value=MagicMock(model_dump=lambda: {"branch": "task/issue-999"})
    )

    # Mock worktree resolution
    with patch("vibe3.services.flow_orchestrator_service.WorktreeManager") as mock_wm:
        mock_ctx = MagicMock()
        mock_ctx.path = Path("/tmp/worktrees/task/issue-999")
        mock_wm.return_value.resolve_bootstrap_worktree_context.return_value = mock_ctx

        issue = IssueInfo(number=999, title="Test", labels=[], state=IssueState.READY)
        service.bootstrap_issue_flow(
            issue, branch="task/issue-999", ensure_worktree=True
        )

    # Verify worktree_path was persisted to store
    store.update_flow_state.assert_any_call(
        "task/issue-999", worktree_path=str(mock_ctx.path)
    )


def test_rebuild_stale_issue_flow_delegates_to_flow_rebuild_usecase() -> None:
    config = load_orchestra_config()
    github = MagicMock()
    github.list_prs_for_branch = MagicMock(return_value=[])
    service = FlowOrchestratorService(
        config, store=MagicMock(), git=MagicMock(), github=github
    )
    issue = IssueInfo(number=320, title="Rebuild lifecycle")

    with patch("vibe3.services.flow_rebuild_usecase.FlowRebuildUsecase") as rebuild_cls:
        rebuild = rebuild_cls.return_value
        rebuild.rebuild_issue_flow.return_value = {"branch": "task/issue-320"}

        result = service.rebuild_stale_issue_flow(
            issue,
            branch="task/issue-320",
            slug="custom-320",
            source="check:stale-ready",
        )

    rebuild.rebuild_issue_flow.assert_called_once_with(
        issue=issue,
        branch="task/issue-320",
        slug="custom-320",
        source="check:stale-ready",
        reason="stale flow rebuild",
        include_remote=False,
        ensure_worktree=False,
    )
    assert result == {"branch": "task/issue-320"}


def test_get_pr_for_issue_uses_branch_pr_status_fallback() -> None:
    """HIGH: Fallback must resolve branch PR status through PRService."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        (git_dir / "vibe3").mkdir(parents=True)

        config = load_orchestra_config()
        config.repo = "owner/repo"
        store = MagicMock()
        git = MagicMock()
        git.get_git_common_dir.return_value = str(git_dir)
        github = MagicMock()
        service = FlowOrchestratorService(config, store=store, git=git, github=github)

        # No PR in flow record, trigger standard branch→PR fallback
        service.get_flow_for_issue = MagicMock(return_value=None)
        github.list_all_prs = MagicMock(return_value=[])
        github.list_prs_for_branch = MagicMock(
            return_value=[_pr_response(number=42, branch="task/issue-123")]
        )

        result = service.get_pr_for_issue(123)

        github.list_all_prs.assert_called_once_with(state="all", limit=50)
        github.list_prs_for_branch.assert_called_once_with(
            "task/issue-123", state="all", repo=None
        )
        assert result == 42


def test_get_pr_for_issue_returns_flow_pr_without_github_call() -> None:
    """If PR in flow record, GitHub API should not be called."""
    config = load_orchestra_config()
    store = MagicMock()
    github = MagicMock()
    service = FlowOrchestratorService(config, store=store, github=github)

    # PR already in flow record
    service.get_flow_for_issue = MagicMock(
        return_value={"pr_number": 99, "branch": "dev/issue-123"}
    )

    result = service.get_pr_for_issue(123)

    # GitHub list_prs_for_branch should NOT be called (fast path from flow)
    github.list_prs_for_branch.assert_not_called()
    assert result == 99


def test_bootstrap_issue_flow_cleans_up_orphan_branch_on_failure() -> None:
    """CRITICAL: Verify complete cleanup when bootstrap fails after branch creation."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    # Initial check: branch doesn't exist, so bootstrap creates it
    # After creation, cleanup checks again: branch exists now, so delete it
    git.branch_exists.side_effect = [
        False,
        True,
    ]  # First call: create, second call: cleanup
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = None
    service = FlowOrchestratorService(config, store=store, git=git, github=github)

    # Simulate failure after branch creation
    service.flow_service.create_flow = MagicMock(
        side_effect=RuntimeError("Database connection failed")
    )

    with pytest.raises(RuntimeError, match="Database connection failed"):
        service.bootstrap_issue_flow(
            IssueInfo(number=999, title="Bootstrap failure test"),
            branch="dev/issue-999",
            source="skill",
        )

    # Verify branch was created (first call to branch_exists returned False)
    git.create_branch_ref.assert_called_once()
    # CRITICAL: Verify cleanup deletes the newly created branch
    # cleanup_flow_scene checks branch_exists (returns True), then calls delete_branch
    git.delete_branch.assert_called_once_with(
        "dev/issue-999", force=True, skip_if_worktree=False
    )


def test_bootstrap_issue_flow_preserves_existing_branch_on_failure() -> None:
    """CRITICAL: Existing branch is still deleted during cleanup
    to ensure no orphan flow_state."""
    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    # Branch already exists before bootstrap starts
    git.branch_exists.return_value = True
    git.get_git_common_dir.return_value = "/tmp/repo/.git"
    store.get_flow_state.return_value = None
    service = FlowOrchestratorService(config, store=store, git=git, github=github)

    # Simulate failure
    service.flow_service.create_flow = MagicMock(
        side_effect=RuntimeError("Flow creation failed")
    )

    with pytest.raises(RuntimeError, match="Flow creation failed"):
        service.bootstrap_issue_flow(
            IssueInfo(number=888, title="Existing branch test"),
            branch="dev/issue-888",
            source="skill",
        )

    # Branch was NOT created (already existed)
    git.create_branch_ref.assert_not_called()
    # CRITICAL: cleanup_flow_scene still attempts to delete the branch
    # This is CORRECT behavior - we must clean up flow_state + branch
    # to avoid leaving orphan records after bootstrap failure
    git.delete_branch.assert_called_once_with(
        "dev/issue-888", force=True, skip_if_worktree=False
    )


def test_rebuild_stale_issue_flow_returns_none_when_pr_already_merged() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        (git_dir / "vibe3").mkdir(parents=True)

        config = load_orchestra_config()
        git = MagicMock()
        git.get_git_common_dir.return_value = str(git_dir)
        github = MagicMock()
        github.list_all_prs = MagicMock(return_value=[])
        github.list_prs_for_branch = MagicMock(
            return_value=[
                _pr_response(
                    number=987,
                    branch="task/issue-321",
                    state=PRState.MERGED,
                )
            ]
        )
        github.get_pr.return_value = MagicMock(
            state=PRState.MERGED, merged_at="2026-05-17T00:00:00Z"
        )
        service = FlowOrchestratorService(
            config, store=MagicMock(), git=git, github=github
        )
        issue = IssueInfo(number=321, title="Merged already")
        service.get_pr_for_issue = MagicMock(return_value=987)

        result = service.rebuild_stale_issue_flow(
            issue, branch="task/issue-321", slug="issue-321"
        )

        assert result is None
