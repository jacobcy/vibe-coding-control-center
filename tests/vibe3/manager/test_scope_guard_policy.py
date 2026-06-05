"""Manager scope guard policy tests."""

from pathlib import Path


def test_audit_branch_validation_uses_merge_base_diff() -> None:
    policy = Path("supervisor/policies/run.md").read_text()

    assert "git diff --name-only origin/main...HEAD" in policy
    assert "git diff --name-only origin/main..HEAD" not in policy


def test_manager_scope_violation_requires_real_violation_check() -> None:
    manager = Path("supervisor/manager.md").read_text()

    assert "git diff main...HEAD --stat" in manager
    assert "必须先核查是否为真实 scope violation" in manager
    assert "不要把已合并 PR 或 main 前进带来的差异误判为当前 issue 越界" in manager


def test_scope_boundary_cross_check_requires_real_violation_check() -> None:
    manager = Path("supervisor/manager.md").read_text()
    cross_check = manager.split("**Scope Boundary Cross-check（新增）**：", 1)[1].split(
        "若 plan 不达标", 1
    )[0]

    assert "若发现疑似 scope violation" in cross_check
    assert "只有确认当前 issue 的实际变更违反 plan Scope Boundary 时" in cross_check
