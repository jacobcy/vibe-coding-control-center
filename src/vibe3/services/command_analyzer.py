"""Command analyzer - 静态分析命令调用链路（AST，不执行代码）."""

import ast
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from vibe3.exceptions import VibeError


class CommandAnalyzerError(VibeError):
    """命令分析失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Command analysis failed: {details}", recoverable=False)


class CallEdge(BaseModel):
    """调用边（caller -> callee）."""

    caller: str
    callee: str
    line: int


class CommandCallChain(BaseModel):
    """命令调用链路分析结果."""

    command: str
    file_path: str
    calls: list[CallEdge]
    call_depth: int


def _extract_calls(file_path: str, func_name: str) -> list[CallEdge]:
    """从函数中提取所有调用关系（AST 静态分析）.

    Args:
        file_path: Python 文件路径
        func_name: 目标函数名

    Returns:
        调用边列表
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError) as e:
        raise CommandAnalyzerError(f"Cannot parse {file_path}: {e}") from e

    edges: list[CallEdge] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            callee = ""
            if isinstance(child.func, ast.Attribute):
                # obj.method() 形式
                if isinstance(child.func.value, ast.Name):
                    callee = f"{child.func.value.id}.{child.func.attr}"
                else:
                    callee = child.func.attr
            elif isinstance(child.func, ast.Name):
                callee = child.func.id

            if callee:
                edges.append(
                    CallEdge(
                        caller=func_name,
                        callee=callee,
                        line=child.lineno,
                    )
                )

    return edges


def _find_command_file(
    command: str, commands_root: str = "src/vibe3/commands"
) -> str | None:
    """在 commands 目录查找命令对应的文件.

    Args:
        command: 命令名（如 "pr" 或 "flow"）
        commands_root: commands 目录路径

    Returns:
        文件路径或 None
    """
    root = Path(commands_root)
    candidate = root / f"{command}.py"
    return str(candidate) if candidate.exists() else None


def analyze_command(
    command: str,
    subcommand: str | None = None,
    commands_root: str = "src/vibe3/commands",
) -> CommandCallChain:
    """静态分析命令调用链路.

    Args:
        command: 顶层命令（如 "pr"、"flow"）
        subcommand: 子命令（如 "draft"、"merge"）
        commands_root: commands 目录路径

    Returns:
        命令调用链路

    Raises:
        CommandAnalyzerError: 分析失败
    """
    full_cmd = f"{command} {subcommand}" if subcommand else command
    log = logger.bind(domain="command_analyzer", action="analyze", command=full_cmd)
    log.info("Analyzing command call chain")

    file_path = _find_command_file(command, commands_root)
    if not file_path:
        raise CommandAnalyzerError(f"Command file not found: {command}.py")

    target_func = subcommand or command
    calls = _extract_calls(file_path, target_func)

    # 简单估算调用深度（唯一 callee 数量）
    depth = len({e.callee for e in calls})

    result = CommandCallChain(
        command=full_cmd,
        file_path=file_path,
        calls=calls,
        call_depth=depth,
    )
    log.bind(calls=len(calls), depth=depth).success("Command analysis complete")
    return result
