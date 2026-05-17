from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.environment.worktree import WorktreeManager
from vibe3.environment.worktree_context import WorktreeContext
from vibe3.services.bootstrap_context_service import (
    BootstrapContextService,
)


class FakeConfig:
    """Minimal config stub for WorktreeManager tests."""

    pass


def test_worktree_manager_raises_on_creation_failure_when_worktree_requested(
    tmp_path: Path,
) -> None:
    """CRITICAL: When use_worktree=True, creation failure must raise SystemError.

    Previously fell back to repo_path, silently ignoring user's isolation request.
    Now raises SystemError to prevent working on main repo without isolation.
    """
    from vibe3.exceptions import SystemError

    manager = WorktreeManager(config=FakeConfig(), repo_path=tmp_path)

    with patch(
        "vibe3.environment.worktree.find_worktree_for_branch", return_value=None
    ):
        with patch.object(
            manager,
            "acquire_issue_worktree",
            side_effect=RuntimeError("creation failed"),
        ):
            with pytest.raises(SystemError, match="Failed to create worktree"):
                manager.resolve_bootstrap_worktree_context(
                    branch="dev/issue-123",
                    issue_number=123,
                    use_worktree=True,
                )


def test_worktree_manager_raises_on_alignment_failure(tmp_path: Path) -> None:
    """HIGH: Alignment failure must raise error, not return unaligned worktree."""
    from vibe3.exceptions import SystemError

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
            # HIGH: Simulate alignment failure
            with patch.object(manager, "align_auto_scene_to_base", return_value=False):
                with pytest.raises(
                    SystemError, match="Failed to align worktree to base branch"
                ):
                    manager.resolve_bootstrap_worktree_context(
                        branch="dev/issue-123",
                        issue_number=123,
                        use_worktree=True,
                    )


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
    """Guard against introducing a separate monolithic CLI command surface."""
    service = BootstrapContextService()
    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=False,
        wants_worktree=False,
    )

    commands = [action.command for action in plan.actions]
    assert any(cmd.startswith("vibe3 internal bootstrap-flow ") for cmd in commands)
    assert all("vibe3 new" not in cmd for cmd in commands)


def test_plan_includes_baseline_snapshot_for_new_flows() -> None:
    """HIGH: New flows must have baseline snapshot for structure diff."""
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=False,
        wants_worktree=False,
    )

    action_kinds = [action.kind for action in plan.actions]
    assert "snapshot_save" in action_kinds

    # Verify order: bootstrap, snapshot, pr_create, handoff
    assert action_kinds == [
        "bootstrap_flow_scene",
        "snapshot_save",
        "pr_create_optional",
        "handoff_append",
    ]

    # Verify snapshot command
    snapshot_action = next(
        action for action in plan.actions if action.kind == "snapshot_save"
    )
    assert snapshot_action.command == "vibe3 snapshot save --as-baseline"
    assert "baseline" in snapshot_action.reason.lower()


def test_plan_skips_baseline_snapshot_when_pr_exists() -> None:
    """Existing flows (with PR) don't need baseline snapshot."""
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=True,
        wants_worktree=False,
    )

    action_kinds = [action.kind for action in plan.actions]
    assert "snapshot_save" not in action_kinds
    assert action_kinds == ["bootstrap_flow_scene", "handoff_append"]


def test_plan_for_new_branch_bootstrap_uses_shared_service_interface() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=False,
        wants_worktree=False,
    )

    assert [action.kind for action in plan.actions] == [
        "bootstrap_flow_scene",
        "pr_create_optional",
        "handoff_append",
    ]
    assert plan.requires_worktree is False


def test_plan_for_existing_branch_bootstrap_without_pr_creation() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=True,
        wants_worktree=False,
    )

    assert [action.kind for action in plan.actions] == [
        "bootstrap_flow_scene",
        "handoff_append",
    ]


def test_plan_for_worktree_bootstrap_marks_shared_worktree_request() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=False,
        wants_worktree=True,
    )

    assert plan.requires_worktree is True
    assert "--worktree" in plan.actions[0].command


def test_plan_can_encode_related_and_dependency_bindings() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=True,
        wants_worktree=False,
        related_issue_numbers=(456,),
        dependency_issue_numbers=(789,),
    )

    command = plan.actions[0].command
    assert "--related 456" in command
    assert "--dependency 789" in command


def test_bootstrap_plan_uses_internal_bootstrap_adapter() -> None:
    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=False,
        wants_worktree=True,
        related_issue_numbers=(456,),
        dependency_issue_numbers=(789,),
    )

    command = plan.actions[0].command
    assert command == (
        "vibe3 internal bootstrap-flow 123 --branch dev/issue-123 "
        "--source skill --worktree --related 456 --dependency 789"
    )


def test_bootstrap_command_escapes_shell_injection_attacks() -> None:
    """CRITICAL: Verify shlex.quote prevents command injection via branch names."""
    import shlex

    service = BootstrapContextService()

    # Malicious branch name attempting shell injection
    malicious_branch = "dev/issue-123; rm -rf /"

    plan = service.plan_vibe_new_bootstrap(
        target_branch=malicious_branch,
        issue_number=123,
        has_existing_pr=False,
        wants_worktree=False,
    )

    command = plan.actions[0].command

    # The branch name must be quoted to prevent injection
    quoted_branch = shlex.quote(malicious_branch)
    assert quoted_branch in command

    # Verify the raw malicious string is NOT in the command
    assert malicious_branch not in command

    # Verify proper quoting format
    assert f"--branch {quoted_branch}" in command
    assert f"bootstrap-flow {shlex.quote('123')}" in command


def test_bootstrap_command_escapes_malicious_issue_numbers() -> None:
    """CRITICAL: Verify shlex.quote prevents injection via issue numbers."""
    import shlex

    service = BootstrapContextService()

    plan = service.plan_vibe_new_bootstrap(
        target_branch="dev/issue-123",
        issue_number=123,
        has_existing_pr=False,
        wants_worktree=False,
        related_issue_numbers=(456,),
        dependency_issue_numbers=(789,),
    )

    command = plan.actions[0].command

    # All dynamic values should be quoted
    assert shlex.quote("123") in command
    assert shlex.quote("456") in command
    assert shlex.quote("789") in command

    # Raw numbers should also appear (in quoted form)
    assert "123" in command
    assert "456" in command
    assert "789" in command


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
