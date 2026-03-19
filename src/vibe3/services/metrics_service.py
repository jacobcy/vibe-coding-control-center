"""Metrics service - 收集代码量指标，从配置读取限制值."""

import subprocess
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from vibe3.config.loader import get_config
from vibe3.exceptions import VibeError


class MetricsError(VibeError):
    """Metrics 收集失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Metrics collection failed: {details}", recoverable=False)


class FileMetrics(BaseModel):
    """单文件指标."""

    path: str
    loc: int


class LayerMetrics(BaseModel):
    """层级指标汇总."""

    total_loc: int
    file_count: int
    max_file_loc: int
    files: list[FileMetrics]
    limit_total: int
    limit_file_default: int  # 默认限制（warning）
    limit_file_max: int  # 最大限制（error）

    @property
    def total_ok(self) -> bool:
        return self.total_loc <= self.limit_total

    @property
    def file_ok(self) -> bool:
        """最大文件未超过上限."""
        return self.max_file_loc <= self.limit_file_max

    @property
    def warnings(self) -> list[FileMetrics]:
        """超过默认限制但未超过最大限制的文件."""
        return [
            f
            for f in self.files
            if f.loc > self.limit_file_default and f.loc <= self.limit_file_max
        ]

    @property
    def errors(self) -> list[FileMetrics]:
        """超过最大限制的文件."""
        return [f for f in self.files if f.loc > self.limit_file_max]


class MetricsReport(BaseModel):
    """完整指标报告."""

    shell: LayerMetrics
    python: LayerMetrics


def _count_loc(path: str) -> int:
    """统计文件行数（排除空行和注释行）.

    Args:
        path: 文件路径

    Returns:
        有效行数
    """
    try:
        result = subprocess.run(
            ["wc", "-l", path],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip().split()[0])
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return 0


def _collect_files(pattern: str, root: Path) -> list[FileMetrics]:
    """收集匹配文件的行数指标.

    Args:
        pattern: glob 模式
        root: 搜索根目录

    Returns:
        文件指标列表
    """
    files = []
    for p in sorted(root.glob(pattern)):
        if p.is_file():
            loc = _count_loc(str(p))
            files.append(FileMetrics(path=str(p), loc=loc))
    return files


def collect_shell_metrics() -> LayerMetrics:
    """收集 Shell 代码指标（bin/ + lib/）.

    Returns:
        Shell 层指标

    Raises:
        MetricsError: 收集失败
    """
    log = logger.bind(domain="metrics", action="collect_shell")
    log.info("Collecting shell metrics")

    try:
        config = get_config()
        limits = config.code_limits

        root = Path(".")
        files: list[FileMetrics] = []
        for pattern in ["bin/**/*.sh", "lib/**/*.sh", "bin/vibe"]:
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
        raise MetricsError(str(e)) from e


def collect_python_metrics() -> LayerMetrics:
    """收集 Python 代码指标（src/vibe3/）.

    Returns:
        Python 层指标

    Raises:
        MetricsError: 收集失败
    """
    log = logger.bind(domain="metrics", action="collect_python")
    log.info("Collecting python metrics")

    try:
        config = get_config()
        limits = config.code_limits

        root = Path("src/vibe3")
        if not root.exists():
            raise MetricsError("src/vibe3 not found")

        files = _collect_files("**/*.py", root)
        # 排除 __pycache__
        files = [f for f in files if "__pycache__" not in f.path]

        total = sum(f.loc for f in files)
        max_loc = max((f.loc for f in files), default=0)

        result = LayerMetrics(
            total_loc=total,
            file_count=len(files),
            max_file_loc=max_loc,
            files=files,
            limit_total=limits.total_file_loc.v3_python,
            limit_file_default=limits.single_file_loc.default,
            limit_file_max=limits.single_file_loc.max,
        )
        log.bind(total_loc=total, file_count=len(files)).success(
            "Python metrics collected"
        )
        return result

    except MetricsError:
        raise
    except Exception as e:
        raise MetricsError(str(e)) from e


def collect_metrics() -> MetricsReport:
    """收集完整指标报告.

    Returns:
        完整指标报告
    """
    logger.bind(domain="metrics", action="collect_all").info("Collecting all metrics")
    return MetricsReport(
        shell=collect_shell_metrics(),
        python=collect_python_metrics(),
    )
