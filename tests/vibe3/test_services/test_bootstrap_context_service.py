from vibe3.services.bootstrap_context_service import (
    BootstrapContextService,
)


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
        "git_checkout_branch",
        "flow_update",
        "flow_bind_task",
        "snapshot_baseline",
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
        "handoff_append",
    ]


def test_plan_for_worktree_bootstrap_marks_environment_dependency() -> None:
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
    assert plan.actions[0].kind == "resolve_worktree_context"
