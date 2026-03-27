"""Shell metrics collector 单元测试."""

from pathlib import Path

from vibe3.config.loader import get_config
from vibe3.services.shell_metrics_collector import (
    _collect_files,
    collect_shell_metrics,
)


def _expected_files_from_config():
    config = get_config()
    root = Path(".")
    files = []
    for path in config.code_limits.code_paths.v2_shell:
        pattern = f"{path}**/*.sh" if path.endswith("/") else path
        files.extend(_collect_files(pattern, root))
    return files


class TestShellMetricsCollector:
    """Shell metrics 收集器测试."""

    def test_collects_configured_paths(self) -> None:
        """验证按照配置收集 shell 文件，并覆盖 lib3 路径."""
        metrics = collect_shell_metrics()
        expected_files = _expected_files_from_config()

        actual_paths = {f.path for f in metrics.files}
        expected_paths = {f.path for f in expected_files}

        assert actual_paths == expected_paths, "收集到的文件列表应与配置匹配"
        assert "lib3/vibe.sh" in actual_paths, "lib3/vibe.sh 应该被收集"
        assert any(p.startswith("lib3/") for p in actual_paths), "lib3/ 目录应被收集"
        assert "bin/vibe" in actual_paths, "bin/vibe 应该被收集"

    def test_metrics_match_expected_counts(self) -> None:
        """验证指标数值与实际文件行数一致."""
        metrics = collect_shell_metrics()
        expected_files = _expected_files_from_config()

        expected_total = sum(f.loc for f in expected_files)
        expected_max = max((f.loc for f in expected_files), default=0)

        assert metrics.file_count == len(expected_files)
        assert metrics.total_loc == expected_total
        assert metrics.max_file_loc == expected_max
        assert len(metrics.files) == metrics.file_count
        assert metrics.limit_total > 0
        assert metrics.limit_file_default > 0
        assert metrics.limit_file_max > 0
