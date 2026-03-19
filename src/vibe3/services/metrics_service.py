"""Metrics service - 收集代码量指标，从配置读取限制值."""

import subprocess
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from vibe3.config.loader import get_config
from vibe3.exceptions import VibeError
from vibe3.models.metrics_models import DeadFunctionInfo, FileMetrics


class MetricsError(VibeError):
    """Metrics 收集失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Metrics collection failed: {details}", recoverable=False)


class ScriptsMetrics(BaseModel):
    """Scripts 目录指标（无严格限制）."""

    total_loc: int
    file_count: int
    max_file_loc: int
    files: list[FileMetrics]


class SubdirMetrics(BaseModel):
    """子目录指标（分层展示用）."""

    name: str  # e.g., "services", "clients"
    loc: int
    file_count: int
    max_file_loc: int


class LayerMetrics(BaseModel):
    """层级指标汇总."""

    total_loc: int
    file_count: int
    max_file_loc: int
    files: list[FileMetrics]
    limit_total: int
    limit_file_default: int  # 默认限制（warning）
    limit_file_max: int  # 最大限制（error）
    subdirs: list[SubdirMetrics] = []  # 分层指标（可选）

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
    scripts: ScriptsMetrics | None = None
    dead_functions: list[DeadFunctionInfo] = []


def _count_loc(path: str) -> int:
    """统计文件行数.

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


def collect_scripts_metrics() -> ScriptsMetrics:
    """收集 Scripts 代码指标（scripts/）.

    Returns:
        Scripts 层指标

    Raises:
        MetricsError: 收集失败
    """
    log = logger.bind(domain="metrics", action="collect_scripts")
    log.info("Collecting scripts metrics")

    try:
        config = get_config()
        paths = config.code_limits.scripts_paths.v2_shell

        root = Path(".")
        files: list[FileMetrics] = []
        for path in paths:
            # 移除末尾的斜杠
            path = path.rstrip("/")
            p = root / path
            if p.is_dir():
                for ext in ["*.sh", "*.py"]:
                    files.extend(_collect_files(f"{path}/**/{ext}", root))
            elif p.is_file():
                loc = _count_loc(str(p))
                files.append(FileMetrics(path=str(p), loc=loc))

        total = sum(f.loc for f in files)
        max_loc = max((f.loc for f in files), default=0)

        result = ScriptsMetrics(
            total_loc=total,
            file_count=len(files),
            max_file_loc=max_loc,
            files=files,
        )
        log.bind(total_loc=total, file_count=len(files)).success(
            "Scripts metrics collected"
        )
        return result

    except Exception as e:
        raise MetricsError(str(e)) from e


def _collect_python_subdir_metrics(files: list[FileMetrics]) -> list[SubdirMetrics]:
    """计算 Python 子目录的分层指标.

    Args:
        files: Python 文件列表

    Returns:
        子目录指标列表
    """
    # 按子目录分组
    subdir_map: dict[str, list[FileMetrics]] = {}
    for f in files:
        # 提取 src/vibe3/ 下的第一级子目录
        parts = Path(f.path).parts
        if len(parts) >= 3 and parts[0] == "src" and parts[1] == "vibe3":
            subdir = parts[2] if len(parts) > 3 else "root"
            if subdir not in subdir_map:
                subdir_map[subdir] = []
            subdir_map[subdir].append(f)

    # 计算每个子目录的指标
    results = []
    for name in sorted(subdir_map.keys()):
        subfiles = subdir_map[name]
        total = sum(f.loc for f in subfiles)
        max_loc = max((f.loc for f in subfiles), default=0)
        results.append(
            SubdirMetrics(
                name=name,
                loc=total,
                file_count=len(subfiles),
                max_file_loc=max_loc,
            )
        )
    return results


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

        # 计算子目录分层指标
        subdirs = _collect_python_subdir_metrics(files)

        result = LayerMetrics(
            total_loc=total,
            file_count=len(files),
            max_file_loc=max_loc,
            files=files,
            limit_total=limits.total_file_loc.v3_python,
            limit_file_default=limits.single_file_loc.default,
            limit_file_max=limits.single_file_loc.max,
            subdirs=subdirs,
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
    from vibe3.services.dead_code_detector import detect_dead_functions
    from vibe3.services.shell_metrics_collector import collect_shell_metrics

    log = logger.bind(domain="metrics", action="collect_all")
    log.info("Collecting all metrics")

    shell = collect_shell_metrics()
    python = collect_python_metrics()
    scripts = collect_scripts_metrics()

    # 检测死函数（可能耗时，仅在有 Python 文件时执行）
    dead_functions: list[DeadFunctionInfo] = []
    try:
        dead_functions = detect_dead_functions(python.files)
        log.bind(dead_count=len(dead_functions)).debug(
            "Dead function detection complete"
        )
    except Exception as e:
        log.bind(error=str(e)).warning("Dead function detection failed, skipping")

    return MetricsReport(
        shell=shell,
        python=python,
        scripts=scripts,
        dead_functions=dead_functions,
    )
