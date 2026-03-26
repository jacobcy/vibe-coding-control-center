"""Command analyzer - 静态分析命令调用链路（AST，不执行代码）."""

import ast
from pathlib import Path
from typing import Set

from loguru import logger
from pydantic import BaseModel

from vibe3.exceptions import VibeError
from vibe3.models.inspection import CallNode, CommandInspection
from vibe3.services.command_analyzer_helpers import (
    find_callee_file,
    find_command_file,
    should_expand,
    should_show_in_tree,
)


class CommandAnalyzerError(VibeError):
    """命令分析失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Command analysis failed: {details}", recoverable=False)


class CallEdge(BaseModel):
    """调用边（caller -> callee）."""

    caller: str
    callee: str
    line: int


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

    file_path = find_command_file(command, subcommand, commands_root)
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

    # Build call nodes, filtering out noise
    nodes: list[CallNode] = []
    for edge in edges:
        # Filter out decorators, builtins, and noise
        if not should_show_in_tree(edge.callee):
            continue

        node = CallNode(name=edge.callee, line=edge.line)

        # Recursively expand if should expand
        if should_expand(edge.callee):
            # Try to find the callee file
            callee_file = find_callee_file(edge.callee, file_path)
            if callee_file:
                node.calls = build_call_tree(
                    callee_file, edge.callee, visited, max_depth - 1
                )

        nodes.append(node)

    return nodes


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
