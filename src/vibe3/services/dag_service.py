"""DAG service - 分析模块依赖图，确认改动影响范围."""

import ast
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from vibe3.exceptions import VibeError


class DAGError(VibeError):
    """DAG 分析失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"DAG analysis failed: {details}", recoverable=False)


class ModuleNode(BaseModel):
    """模块节点."""

    module: str
    file_path: str
    imports: list[str]


class ImpactGraph(BaseModel):
    """影响范围图."""

    seed_modules: list[str]
    impacted_modules: list[str]
    edges: dict[str, list[str]]


def _file_to_module(file_path: str, root: str = "src") -> str:
    """将文件路径转换为模块名.

    Args:
        file_path: 文件路径（如 src/vibe3/services/flow_service.py）
        root: 源码根目录

    Returns:
        模块名（如 vibe3.services.flow_service）
    """
    p = Path(file_path)
    parts = p.with_suffix("").parts
    # 找到 root 之后的部分
    try:
        idx = list(parts).index(root)
        return ".".join(parts[idx + 1 :])
    except ValueError:
        return str(p.with_suffix("")).replace("/", ".")


def _extract_imports(file_path: str) -> list[str]:
    """从 Python 文件提取 import 的模块名.

    Args:
        file_path: Python 文件路径

    Returns:
        导入的模块名列表（仅 vibe3 内部模块）
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("vibe3"):
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("vibe3"):
                imports.append(node.module)
    return imports


def build_module_graph(src_root: str = "src/vibe3") -> dict[str, ModuleNode]:
    """解析 import 构建模块依赖图.

    Args:
        src_root: 源码根目录

    Returns:
        模块名 -> ModuleNode 的映射

    Raises:
        DAGError: 构建失败
    """
    log = logger.bind(domain="dag", action="build_module_graph", src_root=src_root)
    log.info("Building module graph")

    root = Path(src_root)
    if not root.exists():
        raise DAGError(f"Source root not found: {src_root}")

    graph: dict[str, ModuleNode] = {}
    for py_file in sorted(root.glob("**/*.py")):
        if "__pycache__" in str(py_file):
            continue
        module = _file_to_module(str(py_file))
        imports = _extract_imports(str(py_file))
        graph[module] = ModuleNode(
            module=module,
            file_path=str(py_file),
            imports=imports,
        )

    log.bind(module_count=len(graph)).success("Module graph built")
    return graph


def expand_impacted_modules(
    seed_files: list[str],
    graph: dict[str, ModuleNode] | None = None,
) -> ImpactGraph:
    """从 seed 文件扩展影响范围（向上游传播）.

    Args:
        seed_files: 改动的文件列表
        graph: 预构建的模块图（None 则自动构建）

    Returns:
        影响范围图

    Raises:
        DAGError: 分析失败
    """
    log = logger.bind(
        domain="dag", action="expand_impacted", seed_count=len(seed_files)
    )
    log.info("Expanding impacted modules")

    try:
        if graph is None:
            graph = build_module_graph()

        # seed 模块（只取 Python 文件）
        seeds = [
            _file_to_module(f)
            for f in seed_files
            if f.endswith(".py") and "__pycache__" not in f
        ]

        # 构建反向依赖图（谁依赖了我）
        reverse: dict[str, list[str]] = {m: [] for m in graph}
        for module, node in graph.items():
            for dep in node.imports:
                # dep 可能是 vibe3.services.flow_service，精确匹配
                if dep in reverse:
                    reverse[dep].append(module)

        # BFS 向上扩展
        impacted: set[str] = set(seeds)
        queue = list(seeds)
        while queue:
            current = queue.pop(0)
            for upstream in reverse.get(current, []):
                if upstream not in impacted:
                    impacted.add(upstream)
                    queue.append(upstream)

        result = ImpactGraph(
            seed_modules=seeds,
            impacted_modules=sorted(impacted),
            edges={m: reverse.get(m, []) for m in impacted},
        )
        log.bind(
            seeds=len(seeds),
            impacted=len(impacted),
        ).success("Impact expansion complete")
        return result

    except DAGError:
        raise
    except Exception as e:
        raise DAGError(str(e)) from e
