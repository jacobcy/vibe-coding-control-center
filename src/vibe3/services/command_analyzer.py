"""Command analyzer - 静态分析命令调用链路（AST，不执行代码）."""

import ast
from pathlib import Path
from typing import Set

from loguru import logger
from pydantic import BaseModel

from vibe3.exceptions import VibeError
from vibe3.models.inspection import CallNode, CommandInspection


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
) -> CommandInspection:
    """静态分析命令调用链路.

    Args:
        command: 顶层命令（如 "pr"、"flow"）
        subcommand: 子命令（如 "draft"、"merge"）
        commands_root: commands 目录路径

    Returns:
        命令检查结果（包含层次化调用树）

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

    # Build hierarchical call tree
    visited: Set[tuple[str, str]] = set()
    call_tree = build_call_tree(file_path, target_func, visited)

    # Calculate max depth
    depth = _calculate_max_depth(call_tree)

    result = CommandInspection(
        command=full_cmd,
        file=file_path,
        call_depth=depth,
        call_tree=call_tree,
    )
    log.bind(calls=len(call_tree), depth=depth).success("Command analysis complete")
    return result


def build_call_tree(
    file_path: str,
    func_name: str,
    visited: Set[tuple[str, str]],
    max_depth: int = 10,
) -> list[CallNode]:
    """递归构建调用树.

    Args:
        file_path: Python 文件路径
        func_name: 目标函数名
        visited: 已访问的 (file, func) 集合（防止循环）
        max_depth: 最大递归深度

    Returns:
        调用节点列表
    """
    # Prevent infinite recursion
    key = (file_path, func_name)
    if key in visited or max_depth <= 0:
        return []

    visited.add(key)

    # Extract call edges
    try:
        edges = _extract_calls(file_path, func_name)
    except CommandAnalyzerError:
        return []

    # Build call nodes
    nodes: list[CallNode] = []
    for edge in edges:
        node = CallNode(name=edge.callee, line=edge.line)

        # Recursively expand if should expand
        if should_expand(edge.callee):
            # Try to find the callee file
            callee_file = _find_callee_file(edge.callee, file_path)
            if callee_file:
                node.calls = build_call_tree(
                    callee_file, edge.callee, visited, max_depth - 1
                )

        nodes.append(node)

    return nodes


def should_expand(callee: str) -> bool:
    """判断是否应该展开某个调用.

    Args:
        callee: 调用目标名称

    Returns:
        是否应该展开
    """
    # Don't expand built-in or standard library calls
    builtin_prefixes = (
        "logger.",
        "print",
        "len",
        "str",
        "int",
        "dict",
        "list",
        "typer.",
        "json.",
        "yaml.",
    )

    for prefix in builtin_prefixes:
        if callee.startswith(prefix) or callee == prefix.rstrip("."):
            return False

    # Expand service, client, and helper calls
    expand_patterns = ("service.", "client.", "_client", "helper", "ops")
    return any(pattern in callee for pattern in expand_patterns)


def _find_callee_file(callee: str, caller_file: str) -> str | None:
    """查找被调用函数所在的文件.

    Args:
        callee: 调用目标名称（如 "service.get_pr"）
        caller_file: 调用者文件路径

    Returns:
        被调用者文件路径或 None
    """
    # Heuristic: look for patterns like "service.xxx" -> "services/xxx_service.py"
    parts = callee.split(".")
    if len(parts) >= 2:
        obj_name = parts[0]

        # Common patterns
        patterns = [
            f"src/vibe3/services/{obj_name}_service.py",
            f"src/vibe3/clients/{obj_name}_client.py",
            f"src/vibe3/clients/{obj_name}_ops.py",
        ]

        for pattern in patterns:
            if Path(pattern).exists():
                return pattern

    return None


def _calculate_max_depth(nodes: list[CallNode]) -> int:
    """计算调用树的最大深度.

    Args:
        nodes: 调用节点列表

    Returns:
        最大深度
    """
    if not nodes:
        return 0

    max_child_depth = 0
    for node in nodes:
        if node.calls:
            child_depth = _calculate_max_depth(node.calls)
            max_child_depth = max(max_child_depth, child_depth)

    return 1 + max_child_depth
