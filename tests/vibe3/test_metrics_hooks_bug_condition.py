"""Bug Condition 探索性测试 - 确认三个 bug 存在.

这些测试在**未修复代码**上运行，FAIL 即为成功（证明 bug 存在）。
不要修复任何代码，只记录反例。

Validates: Requirements 1.1, 1.2, 1.3, 1.4
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Bug 1: pre-push 漏检
# ---------------------------------------------------------------------------


def test_bug1_prepush_missing_shell_loc_check():
    """Bug Condition: pre-push.sh 不调用 check-shell-loc.sh.

    预期 FAIL（证明 bug 存在）：pre-push.sh 中无 check-shell-loc 调用。
    """
    content = Path("scripts/hooks/pre-push.sh").read_text()
    # 这个断言应该 FAIL（证明 bug 存在）
    assert (
        "check-shell-loc" in content
    ), "BUG CONFIRMED: pre-push.sh 漏掉 check-shell-loc.sh 调用"


# ---------------------------------------------------------------------------
# Bug 2: metrics_service 孤岛
# ---------------------------------------------------------------------------


def test_bug2_check_python_loc_uses_own_logic():
    """Bug Condition: check-python-loc.sh 不调用 metrics_service.

    预期 FAIL（证明 bug 存在）：check-python-loc.sh 使用独立 find+wc 逻辑。
    """
    content = Path("scripts/hooks/check-python-loc.sh").read_text()
    assert (
        "metrics_service" in content
    ), "BUG CONFIRMED: check-python-loc.sh 未使用 metrics_service"


def test_bug2_check_shell_loc_uses_own_logic():
    """Bug Condition: check-shell-loc.sh 不调用 metrics_service.

    预期 FAIL（证明 bug 存在）：check-shell-loc.sh 使用独立 find+wc 逻辑。
    """
    content = Path("scripts/hooks/check-shell-loc.sh").read_text()
    assert (
        "metrics_service" in content
    ), "BUG CONFIRMED: check-shell-loc.sh 未使用 metrics_service"


# ---------------------------------------------------------------------------
# Bug 3: hooks list 静态化
# ---------------------------------------------------------------------------


def test_bug3_hooks_list_shows_live_metrics(capsys):
    """Bug Condition: vibe hooks list 不展示实际 LOC 数值.

    预期 FAIL（证明 bug 存在）：list_hooks() 输出不含动态 LOC 数值。
    """
    from vibe3.commands.hooks import list_hooks
    from vibe3.services.metrics_service import collect_metrics

    report = collect_metrics()
    list_hooks()
    captured = capsys.readouterr()

    # 这个断言应该 FAIL（证明 bug 存在）
    assert (
        str(report.shell.total_loc) in captured.out
    ), f"BUG CONFIRMED: hooks list 不含实际 shell LOC 数值 ({report.shell.total_loc})"
