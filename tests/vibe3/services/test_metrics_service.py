"""MetricsService 单元测试."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.config.loader import get_config
from vibe3.services.metrics_service import (
    FileMetrics,
    LayerMetrics,
    MetricsError,
    collect_python_metrics,
)

# 测试常量
MOCK_FILES = [
    FileMetrics(path="src/vibe3/services/flow_service.py", loc=120),
    FileMetrics(path="src/vibe3/services/pr_service.py", loc=80),
]


def get_v2_limits():
    """获取 V2 Shell 配置限制."""
    config = get_config()
    return config.code_limits.v2_shell


def get_v3_limits():
    """获取 V3 Python 配置限制."""
    config = get_config()
    return config.code_limits.v3_python


class TestLayerMetrics:
    """LayerMetrics 模型测试."""

    def test_total_ok_within_limit(self) -> None:
        limits = get_v3_limits()
        m = LayerMetrics(
            total_loc=100,
            file_count=2,
            max_file_loc=80,
            files=MOCK_FILES,
            limit_total=limits.total_loc,
            limit_file=limits.max_file_loc,
        )
        assert m.total_ok is True

    def test_total_ok_exceeds_limit(self) -> None:
        limits = get_v3_limits()
        m = LayerMetrics(
            total_loc=limits.total_loc + 1000,
            file_count=2,
            max_file_loc=80,
            files=MOCK_FILES,
            limit_total=limits.total_loc,
            limit_file=limits.max_file_loc,
        )
        assert m.total_ok is False

    def test_violations_detected(self) -> None:
        limits = get_v3_limits()
        files = [FileMetrics(path="big.py", loc=limits.max_file_loc + 100)]
        m = LayerMetrics(
            total_loc=limits.max_file_loc + 100,
            file_count=1,
            max_file_loc=limits.max_file_loc + 100,
            files=files,
            limit_total=limits.total_loc,
            limit_file=limits.max_file_loc,
        )
        assert len(m.violations) == 1
        assert m.violations[0].path == "big.py"

    def test_no_violations(self) -> None:
        limits = get_v3_limits()
        m = LayerMetrics(
            total_loc=200,
            file_count=2,
            max_file_loc=120,
            files=MOCK_FILES,
            limit_total=limits.total_loc,
            limit_file=limits.max_file_loc,
        )
        assert m.violations == []


class TestCollectPythonMetrics:
    """collect_python_metrics 测试."""

    def test_returns_layer_metrics(self, tmp_path) -> None:
        # Arrange: 创建临时 Python 文件
        src = tmp_path / "vibe3" / "services"
        src.mkdir(parents=True)
        (src / "foo.py").write_text("def foo():\n    pass\n")

        limits = get_v3_limits()

        with patch("vibe3.services.metrics_service.Path") as mock_path_cls:
            mock_root = MagicMock()
            mock_root.exists.return_value = True
            mock_root.glob.return_value = [src / "foo.py"]
            mock_path_cls.return_value = mock_root

            with patch("vibe3.services.metrics_service._count_loc", return_value=3):
                result = collect_python_metrics()

        assert result.file_count >= 0
        assert result.limit_total == limits.total_loc

    def test_raises_when_src_missing(self) -> None:
        with patch("vibe3.services.metrics_service.Path") as mock_path_cls:
            mock_root = MagicMock()
            mock_root.exists.return_value = False
            mock_path_cls.return_value = mock_root

            with pytest.raises(MetricsError, match="not found"):
                collect_python_metrics()
