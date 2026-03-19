"""Shell metrics collector - 收集 Shell (v2) 代码指标."""

import subprocess
from pathlib import Path

from loguru import logger

from vibe3.config.loader import get_config
from vibe3.exceptions import VibeError
from vibe3.models.metrics_models import FileMetrics
from vibe3.services.metrics_service import LayerMetrics


class ShellMetricsError(VibeError):
    """Shell metrics 收集失败."""

    def __init__(self, details: str) -> None:
        super().__init__(
            f"Shell metrics collection failed: {details}", recoverable=False
        )


def collect_shell_metrics() -> LayerMetrics:
    """收集 Shell 代码指标.

    路径来源: config.code_limits.code_paths.v2_shell
    - 目录路径 (如 "lib/") 会自动展开为 "**/*.sh"
    - 文件路径 (如 "bin/vibe") 直接使用

    Returns:
        Shell 层指标

    Raises:
        ShellMetricsError: 收集失败
    """
    log = logger.bind(domain="metrics", action="collect_shell")
    log.info("Collecting shell metrics")

    try:
        config = get_config()
        limits = config.code_limits

        root = Path(".")
        files: list[FileMetrics] = []

        # 从配置真源读取 Shell 代码路径
        for path in limits.code_paths.v2_shell:
            # 判断是目录还是文件
            if path.endswith("/"):
                # 目录路径: lib/ -> lib/**/*.sh
                pattern = f"{path}**/*.sh"
            else:
                # 文件路径: bin/vibe -> bin/vibe
                pattern = path
            files.extend(_collect_files(pattern, root))

        total = sum(f.loc for f in files)
        max_loc = max((f.loc for f in files), default=0)

        result = LayerMetrics(
            total_loc=total,
            file_count=len(files),
            max_file_loc=max_loc,
            files=files,
            limit_total=limits.total_file_loc.v2_shell,
            limit_file_default=limits.single_file_loc.default,
            limit_file_max=limits.single_file_loc.max,
        )
        log.bind(total_loc=total, file_count=len(files)).success(
            "Shell metrics collected"
        )
        return result

    except Exception as e:
        raise ShellMetricsError(str(e)) from e


def _collect_files(pattern: str, root: Path) -> list[FileMetrics]:
    """收集匹配文件的行数指标（仅用于 shell）.

    Args:
        pattern: glob 模式
        root: 搜索根目录

    Returns:
        文件指标列表
    """
    files = []
    for p in sorted(root.glob(pattern)):
        if p.is_file():
            try:
                result = subprocess.run(
                    ["wc", "-l", str(p)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                loc = int(result.stdout.strip().split()[0])
            except (subprocess.CalledProcessError, ValueError, IndexError):
                loc = 0
            files.append(FileMetrics(path=str(p), loc=loc))
    return files
