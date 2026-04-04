"""DAG service - 分析模块依赖图，确认改动影响范围."""

import ast
from collections import deque
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
                # 处理 "from vibe3.analysis import dag_service" 的情况
                # 尝试组合完整模块路径，如果存在于模块图中则记录
                for alias in node.names:
                    full_module = f"{node.module}.{alias.name}"
                    # 检查是否可能是子模块（启发式：首字母小写）
                    if alias.name[0].islower():
                        imports.append(full_module)
                    else:
                        # 可能是类或函数，只记录模块
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
    max_depth: int | None = None,
    hub_fanout_threshold: int | None = None,
) -> ImpactGraph:
    """从 seed 文件扩展影响范围（向上游传播）.

    Args:
        seed_files: 改动的文件列表
        graph: 预构建的模块图（None 则自动构建）
        max_depth: BFS 最大跳数（None 表示无限制）。
            用于 pre-push 测试选择，防止从 hub 模块爆开到全量。
        hub_fanout_threshold: 反向依赖数超过此阈值的模块视为 hub，
            不再向上扩展（None 表示不限制）。
            典型值 15：防止 cli.py、__init__.py 等 hub 拉入全量模块。

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

        # BFS 向上扩展（带深度限制和 hub 豁免）
        impacted: set[str] = set(seeds)
        queue: deque[tuple[str, int]] = deque((s, 0) for s in seeds)
        while queue:
            current, depth = queue.popleft()

            # Hub 豁免：高 fanout 节点不向上扩展
            if (
                hub_fanout_threshold is not None
                and len(reverse.get(current, [])) > hub_fanout_threshold
            ):
                continue

            # 深度限制检查
            if max_depth is not None and depth >= max_depth:
                continue

            for upstream in reverse.get(current, []):
                if upstream not in impacted:
                    impacted.add(upstream)
                    queue.append((upstream, depth + 1))

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
