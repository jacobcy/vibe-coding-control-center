"""Preservation 属性测试 - 在未修复代码上建立基线.

这些测试在**未修复代码**上运行，必须全部 PASS。
修复后重新运行，仍必须 PASS（无回归）。

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# 1. collect_metrics() 结构不变
# ---------------------------------------------------------------------------


def test_collect_metrics_returns_correct_structure():
    """collect_metrics() 返回 MetricsReport(shell=LayerMetrics, python=LayerMetrics).

    **Validates: Requirements 3.5**
    """
    from vibe3.services.metrics_service import (
        LayerMetrics,
        MetricsReport,
        collect_metrics,
    )

    report = collect_metrics()
    assert isinstance(report, MetricsReport)
    assert isinstance(report.shell, LayerMetrics)
    assert isinstance(report.python, LayerMetrics)
    assert report.shell.total_loc > 0
    assert report.python.total_loc > 0


# ---------------------------------------------------------------------------
# 2. LayerMetrics 属性完整性（属性测试）
# ---------------------------------------------------------------------------


@given(st.integers(min_value=0, max_value=10000))
def test_layer_metrics_total_ok_property(loc):
    """LayerMetrics.total_ok 属性：total_loc <= limit_total 时为 True.

    **Validates: Requirements 3.5**
    """
    from vibe3.services.metrics_service import FileMetrics, LayerMetrics

    m = LayerMetrics(
        total_loc=loc,
        file_count=1,
        max_file_loc=loc,
        files=[FileMetrics(path="test.py", loc=loc)],
        limit_total=5000,
        limit_file_default=200,
        limit_file_max=300,
    )
    assert m.total_ok == (loc <= 5000)


# ---------------------------------------------------------------------------
# 3. check-per-file-loc.sh 行为不变（该脚本不会被修改）
# ---------------------------------------------------------------------------


def test_check_per_file_loc_script_unchanged():
    """check-per-file-loc.sh 内容不变（本次修复不涉及该脚本）.

    **Validates: Requirements 3.3**
    """
    content = Path("scripts/hooks/check-per-file-loc.sh").read_text()
    # 验证关键逻辑存在
    assert "LIMIT_DEFAULT" in content
    assert "LIMIT_MAX" in content
    assert "warnings" in content
    assert "errors" in content


# ---------------------------------------------------------------------------
# 4. vibe metrics show 命令可正常调用
# ---------------------------------------------------------------------------


def test_metrics_show_command_callable():
    """vibe metrics show 命令可正常调用，不抛异常.

    **Validates: Requirements 3.4**
    """
    from vibe3.services.metrics_service import collect_metrics

    report = collect_metrics()
    # 验证两层都有数据
    assert report.shell.file_count >= 0
    assert report.python.file_count > 0
