"""Dead code detection service - 检测潜在的死函数."""

import sys
from io import StringIO

from loguru import logger

from vibe3.models.metrics_models import DeadFunctionInfo, FileMetrics

# 已知非死函数的模式（框架/动态调用的函数）
_SKIP_PATTERNS = [
    "render_",  # UI 渲染函数（typer/rich 框架调用）
    "format_",  # 格式化函数
    "_main",  # 主入口
    "main",  # 主入口
    "test_",  # 测试函数
    "_test",  # 测试函数
    "app",  # Typer/FastAPI app
]


def _should_skip(name: str) -> bool:
    """检查函数名是否应该跳过死函数检测."""
    for pattern in _SKIP_PATTERNS:
        if name.startswith(pattern) or name.endswith(pattern):
            return True
    return False


def detect_dead_functions(python_files: list[FileMetrics]) -> list[DeadFunctionInfo]:
    """检测潜在的死函数（0 引用的函数）.

    Args:
        python_files: Python 文件列表

    Returns:
        死函数信息列表
    """
    from vibe3.services.serena_service import SerenaService

    log = logger.bind(domain="metrics", action="detect_dead_functions")
    log.info("Detecting dead functions")

    dead_funcs: list[DeadFunctionInfo] = []
    serena = SerenaService()

    # 抑制 Serena 的 stderr 警告
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        for f in python_files:
            try:
                # 使用 serena_file_analyzer 分析文件
                result = serena.analyze_file(f.path)
                symbols = result.get("symbols", [])

                for sym in symbols:
                    # 只关注非 CLI 命令且引用为 0 的函数
                    if sym.get("type") == "function" and sym.get("references", 0) == 0:
                        # 跳过已知的非死函数模式
                        if _should_skip(sym["name"]):
                            continue
                        dead_funcs.append(
                            DeadFunctionInfo(
                                name=sym["name"],
                                file=f.path,
                                line=0,  # analyze_file 不返回行号
                                is_cli_candidate=False,
                            )
                        )
            except Exception:
                # 分析失败时跳过该文件
                pass
    finally:
        sys.stderr = old_stderr

    log.bind(dead_count=len(dead_funcs)).success("Dead function detection complete")
    return dead_funcs
