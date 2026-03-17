"""Structure service - 分析文件结构，迁移自 structure_summary.sh."""

import ast
import re
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from vibe3.exceptions import VibeError


class StructureError(VibeError):
    """结构分析失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Structure analysis failed: {details}", recoverable=False)


class FunctionInfo(BaseModel):
    """函数信息."""

    name: str
    line: int
    loc: int


class FileStructure(BaseModel):
    """文件结构分析结果."""

    path: str
    language: str
    total_loc: int
    functions: list[FunctionInfo]
    function_count: int


def analyze_python_file(file_path: str) -> FileStructure:
    """分析 Python 文件结构（AST 解析）.

    Args:
        file_path: 文件路径

    Returns:
        文件结构信息

    Raises:
        StructureError: 解析失败
    """
    log = logger.bind(domain="structure", action="analyze_python", file=file_path)
    log.info("Analyzing Python file")

    path = Path(file_path)
    if not path.exists():
        raise StructureError(f"File not found: {file_path}")

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()

        functions: list[FunctionInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno)
                loc = end_line - node.lineno + 1
                functions.append(
                    FunctionInfo(
                        name=node.name,
                        line=node.lineno,
                        loc=loc,
                    )
                )

        result = FileStructure(
            path=file_path,
            language="python",
            total_loc=len(lines),
            functions=sorted(functions, key=lambda f: f.line),
            function_count=len(functions),
        )
        log.bind(functions=len(functions), loc=len(lines)).success(
            "Python file analyzed"
        )
        return result

    except SyntaxError as e:
        raise StructureError(f"Syntax error in {file_path}: {e}") from e
    except Exception as e:
        raise StructureError(str(e)) from e


def analyze_shell_file(file_path: str) -> FileStructure:
    """分析 Shell 文件结构（正则解析函数定义）.

    Args:
        file_path: 文件路径

    Returns:
        文件结构信息

    Raises:
        StructureError: 解析失败
    """
    log = logger.bind(domain="structure", action="analyze_shell", file=file_path)
    log.info("Analyzing shell file")

    path = Path(file_path)
    if not path.exists():
        raise StructureError(f"File not found: {file_path}")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        # 匹配 function foo() 或 foo() 两种风格
        func_pattern = re.compile(r"^(?:function\s+)?(\w+)\s*\(\s*\)\s*\{?\s*$")

        functions: list[FunctionInfo] = []
        for i, line in enumerate(lines, start=1):
            m = func_pattern.match(line.strip())
            if m:
                functions.append(FunctionInfo(name=m.group(1), line=i, loc=0))

        result = FileStructure(
            path=file_path,
            language="shell",
            total_loc=len(lines),
            functions=functions,
            function_count=len(functions),
        )
        log.bind(functions=len(functions), loc=len(lines)).success(
            "Shell file analyzed"
        )
        return result

    except Exception as e:
        raise StructureError(str(e)) from e


def analyze_file(file_path: str) -> FileStructure:
    """自动检测语言并分析文件结构.

    Args:
        file_path: 文件路径

    Returns:
        文件结构信息
    """
    if file_path.endswith(".py"):
        return analyze_python_file(file_path)
    elif file_path.endswith((".sh", ".zsh", ".bash")):
        return analyze_shell_file(file_path)
    else:
        raise StructureError(f"Unsupported file type: {file_path}")
