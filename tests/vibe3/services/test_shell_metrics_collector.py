"""Shell metrics collector 单元测试."""

from pathlib import Path

from vibe3.services.shell_metrics_collector import collect_shell_metrics


class TestShellMetricsCollector:
    """Shell metrics 收集器测试."""

    def test_collects_lib3_vibe_sh(self) -> None:
        """回归测试: lib3/vibe.sh 必须被包含在 shell metrics 中.

        背景: PR 208 发现 collect_shell_metrics 使用硬编码路径
        ["bin/**/*.sh", "lib/**/*.sh", "bin/vibe"]，导致 lib3/ 被遗漏。
        修复后应该从 config.code_limits.code_paths.v2_shell 读取路径。
        """
        metrics = collect_shell_metrics()

        # 验证 lib3/vibe.sh 在结果中
        lib3_files = [f for f in metrics.files if "lib3" in f.path]
        assert len(lib3_files) > 0, "lib3/ 目录应该被包含在 shell metrics 中"

        # 验证 lib3/vibe.sh 具体文件存在
        lib3_vibe_sh = [f for f in metrics.files if f.path == "lib3/vibe.sh"]
        assert len(lib3_vibe_sh) == 1, "lib3/vibe.sh 应该被收集"
        assert lib3_vibe_sh[0].loc > 0, "lib3/vibe.sh 应该有内容"

    def test_file_count_increased_after_fix(self) -> None:
        """验证修复后文件数量增加.

        修复前: 51 files
        修复后: 应该 >= 52 files (包含 lib3/vibe.sh)
        """
        metrics = collect_shell_metrics()
        # 修复后至少应该有 52 个文件
        assert metrics.file_count >= 52, (
            f"期望至少 52 个文件，实际 {metrics.file_count} 个"
        )

    def test_total_loc_increased_after_fix(self) -> None:
        """验证修复后总行数增加.

        修复前: 6682 LOC
        修复后: 应该 >= 6764 LOC (包含 lib3/vibe.sh 的 82 行)
        """
        metrics = collect_shell_metrics()
        # lib3/vibe.sh 有 82 行，所以至少应该增加这么多
        assert metrics.total_loc >= 6764, (
            f"期望至少 6764 行，实际 {metrics.total_loc} 行"
        )

    def test_uses_config_paths_not_hardcoded(self) -> None:
        """验证使用配置路径而不是硬编码.

        检查是否所有 config.code_limits.code_paths.v2_shell 中的路径
        都被正确处理了。
        """
        from vibe3.config.loader import get_config

        config = get_config()
        expected_paths = config.code_limits.code_paths.v2_shell

        metrics = collect_shell_metrics()

        # 验证 lib/ 和 lib3/ 都有文件被收集
        lib_files = [f for f in metrics.files if f.path.startswith("lib/")]
        lib3_files = [f for f in metrics.files if f.path.startswith("lib3/")]
        bin_vibe = [f for f in metrics.files if f.path == "bin/vibe"]

        assert len(lib_files) > 0, "lib/ 目录应该有文件"
        assert len(lib3_files) > 0, "lib3/ 目录应该有文件"
        assert len(bin_vibe) == 1, "bin/vibe 应该被收集"

    def test_returns_valid_layer_metrics(self) -> None:
        """验证返回的 LayerMetrics 结构正确."""
        metrics = collect_shell_metrics()

        assert metrics.total_loc > 0
        assert metrics.file_count > 0
        assert metrics.max_file_loc > 0
        assert len(metrics.files) == metrics.file_count
        assert metrics.limit_total > 0
        assert metrics.limit_file_default > 0
        assert metrics.limit_file_max > 0
