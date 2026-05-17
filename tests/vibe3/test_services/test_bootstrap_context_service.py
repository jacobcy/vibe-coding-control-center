from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.environment.worktree import WorktreeManager
from vibe3.environment.worktree_context import WorktreeContext
from vibe3.services.bootstrap_context_service import (
    BootstrapContextService,
)


class FakeConfig:
    """Minimal config stub for WorktreeManager tests."""

    pass


def test_worktree_manager_can_describe_bootstrap_context(tmp_path: Path) -> None:
    """Test that resolve_bootstrap_worktree_context returns WorktreeContext."""
    manager = WorktreeManager(config=FakeConfig(), repo_path=tmp_path)

    mock_context = WorktreeContext(
        path=tmp_path / ".worktrees" / "dev-issue-123",
        is_temporary=False,
        branch="dev/issue-123",
        issue_number=123,
    )

    with patch(
        "vibe3.environment.worktree.find_worktree_for_branch", return_value=None
    ):
        with patch.object(manager, "acquire_issue_worktree", return_value=mock_context):
            with patch.object(manager, "align_auto_scene_to_base", return_value=True):
                context = manager.resolve_bootstrap_worktree_context(
                    branch="dev/issue-123",
                    issue_number=123,
                    use_worktree=True,
                )

    assert context.issue_number == 123
    assert context.branch == "dev/issue-123"
    assert context.is_temporary is False


def test_worktree_manager_returns_repo_path_when_no_worktree_needed(
    tmp_path: Path,
) -> None:
    """Test that resolve returns repo_path when use_worktree=False."""
    manager = WorktreeManager(config=FakeConfig(), repo_path=tmp_path)

    context = manager.resolve_bootstrap_worktree_context(
        branch="dev/issue-123",
        issue_number=123,
        use_worktree=False,
    )

    assert context.path == tmp_path
    assert context.issue_number == 123
    assert context.branch == "dev/issue-123"
    assert context.is_temporary is False


def test_bootstrap_plan_references_atomic_cli_commands_only() -> None:
    """Guard against replacing atomic bootstrap commands with monolithic command."""
    service = BootstrapContextService()
    plan = service.plan_vibe_new_bootstrap(
        current_branch="main",
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_flow=False,
        has_existing_pr=False,
        wants_worktree=False,
    )

    commands = [action.command for action in plan.actions]
    assert any(cmd.startswith("vibe3 flow update") for cmd in commands)
    assert any(cmd.startswith("vibe3 flow bind") for cmd in commands)
    assert all("vibe3 new" not in cmd for cmd in commands)


def test_plan_for_new_branch_bootstrap_uses_atomic_actions() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        current_branch="main",
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_flow=False,
        has_existing_pr=False,
        wants_worktree=False,
    )

    assert [action.kind for action in plan.actions] == [
        "ensure_branch",
        "flow_update",
        "flow_bind_task",
        "snapshot_baseline",
        "pr_create_optional",
        "handoff_append",
    ]
    assert plan.requires_worktree is False


def test_plan_for_existing_branch_bootstrap_skips_branch_creation() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        current_branch="dev/issue-123",
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_flow=False,
        has_existing_pr=False,
        wants_worktree=False,
    )

    assert [action.kind for action in plan.actions] == [
        "flow_update",
        "flow_bind_task",
        "snapshot_baseline",
        "pr_create_optional",
        "handoff_append",
    ]


def test_plan_for_worktree_bootstrap_includes_create_worktree_action() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        current_branch="main",
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_flow=False,
        has_existing_pr=False,
        wants_worktree=True,
    )

    assert plan.requires_worktree is True
    # First action is ensure_branch, then create_worktree
    action_kinds = [action.kind for action in plan.actions]
    assert "ensure_branch" in action_kinds
    assert "create_worktree" in action_kinds
    # create_worktree should come after ensure_branch
    branch_idx = action_kinds.index("ensure_branch")
    worktree_idx = action_kinds.index("create_worktree")
    assert worktree_idx > branch_idx


def test_shared_abstraction_used_by_both_orchestra_and_skill(
    tmp_path: Path,
) -> None:
    """Verify both resolve_manager_cwd and resolve_bootstrap_worktree_context
    share the same core logic via _find_or_create_worktree_for_branch."""
    manager = WorktreeManager(config=FakeConfig(), repo_path=tmp_path)

    mock_context = WorktreeContext(
        path=tmp_path / ".worktrees" / "dev-issue-123",
        is_temporary=False,
        branch="dev/issue-123",
        issue_number=123,
    )

    # Create a mock function to track calls
    mock_find_or_create = MagicMock(return_value=mock_context)

    with patch.object(
        manager,
        "_find_or_create_worktree_for_branch",
        mock_find_or_create,
    ):
        with patch.object(manager, "align_auto_scene_to_base", return_value=True):
            # Orchestra path
            orchestra_path, _ = manager.resolve_manager_cwd(123, "task/issue-123")
            # Skill path
            skill_ctx = manager.resolve_bootstrap_worktree_context(
                branch="dev/issue-123",
                issue_number=123,
                use_worktree=True,
            )

    # Both should have called the shared abstraction
    assert mock_find_or_create.call_count == 2
    assert orchestra_path is not None
    assert skill_ctx.issue_number == 123
