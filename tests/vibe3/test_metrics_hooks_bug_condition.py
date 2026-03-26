"""Bug Condition 探索性测试 - 确认三个 bug 存在.

这些测试使用 @pytest.mark.xfail 标记预期失败，用于跟踪已知bug。
当bug修复后，测试应该通过，xfail标记可以移除。

Validates: Requirements 1.1, 1.2, 1.3, 1.4
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bug 1: pre-push 漏检 - FIXED in refactor/split-large-files
# ---------------------------------------------------------------------------


def test_bug1_prepush_missing_shell_loc_check():
    """Verify pre-push.sh includes check-shell-loc.sh call.

    This test should PASS after refactor/split-large-files changes.
    """
    content = Path("scripts/hooks/pre-push.sh").read_text()
    assert "check-shell-loc" in content, "pre-push.sh should call check-shell-loc.sh"


# ---------------------------------------------------------------------------
# Bug 2: metrics_service 孤岛 - FIXED in refactor/split-large-files
# ---------------------------------------------------------------------------


def test_bug2_check_python_loc_uses_own_logic():
    """Verify check-python-loc.sh uses metrics_service.

    This test should PASS after refactor/split-large-files changes.
    """
    content = Path("scripts/hooks/check-python-loc.sh").read_text()
    assert (
        "metrics_service" in content
    ), "check-python-loc.sh should use metrics_service"


def test_bug2_check_shell_loc_uses_own_logic():
    """Verify check-shell-loc.sh uses metrics service.

    This test should PASS after refactor/split-large-files changes.
    """
    content = Path("scripts/hooks/check-shell-loc.sh").read_text()
    # 修复后使用 shell_metrics_collector（metrics 服务的子模块）
    assert (
        "shell_metrics_collector" in content or "metrics_service" in content
    ), "check-shell-loc.sh should use metrics service"


# ---------------------------------------------------------------------------
# Bug 3: hooks list 静态化 - KNOWN BUG, tracked separately
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Bug: vibe hooks list doesn't show live metrics - see issue tracking",
    strict=False,
)
def test_bug3_hooks_list_shows_live_metrics(capsys):
    """Bug: vibe hooks list doesn't show actual LOC values.

    This test is expected to FAIL until bug is fixed.
    When fixed, remove @pytest.mark.xfail decorator.
    """
    from vibe3.commands.hooks import list_hooks
    from vibe3.services.metrics_service import collect_metrics

    report = collect_metrics()
    list_hooks()
    captured = capsys.readouterr()

    # This should pass when bug is fixed
    assert (
        str(report.shell.total_loc) in captured.out
    ), f"hooks list should show shell LOC ({report.shell.total_loc})"
