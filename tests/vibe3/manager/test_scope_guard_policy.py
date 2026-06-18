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


def test_review_policy_contains_path_level_cross_validation() -> None:
    """Verify review.md Section 0 contains path-level cross-validation instructions."""
    review = Path("supervisor/policies/review.md").read_text()

    # Check for section 0 sub-steps (0a, 0b, 0c, 0d)
    assert "0a. 提取 plan 声明的文件路径" in review
    assert "0b. 获取实际变更的文件路径" in review
    assert "0c. 路径级交叉验证" in review
    assert "0d. 判断标准" in review

    # Check for key instructions
    assert "路径级交叉验证" in review
    assert "位置偏差" in review
    assert "新增文件超出 scope" in review
    assert "配置文件/间接文件遗漏" in review

    # Check for correct diff command (merge-base diff)
    assert "git diff main...HEAD --name-only" in review

    # Check for judgment criteria
    assert "以下情况不是 scope violation" in review
    assert "以下情况是 scope violation" in review

    # Check for specific examples
    assert "测试文件自动覆盖" in review
    assert "计划声明的源文件路径与实际创建/修改的源文件路径不一致" in review


def test_plan_policy_requires_full_file_paths_in_changes() -> None:
    """Verify plan.md requires full file paths in Changes section."""
    plan = Path("supervisor/policies/plan.md").read_text()

    # Check that Changes section requires full file paths
    changes_section = plan.split("## 好计划长什么样", 1)[1]
    changes_section = changes_section.split("## 坏计划长什么样", 1)[0]
    assert "Changes" in changes_section
    assert "完整的文件路径" in changes_section or "完整文件路径" in changes_section
