"""Shared fixtures for modularity validation tests."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

# Layer mapping (6 = Infrastructure, 1 = CLI)
# Based on docs/standards/v3-module-architecture-standard.md §2 and §3
MODULE_LAYER_MAP: dict[str, int] = {
    # Layer 6 - Infrastructure & Models（系统基石，严禁依赖上层）
    "adapters": 6,
    "clients": 6,
    "config": 6,
    "exceptions": 6,
    "models": 6,
    "observability": 6,
    "utils": 6,
    # Layer 5 - Environment & Analysis tools（仅依赖 L6 的无状态原语/工具）
    "analysis": 5,
    "environment": 5,
    # Layer 4 - Execution primitives（被编排核心调用的无状态执行原语）
    "agents": 4,
    "prompts": 4,
    # Layer 3 - Orchestration core（编排核心层：事件驱动的业务编排与执行控制）
    # 这 6 个模块构成一个强连通分量（SCC），内部存在已知的循环依赖技术债，
    # 由 test_no_circular_deps_within_l3_core 追踪（Phase 1/2 后仍有内部循环依赖）。
    # 作为同一层，它们对外（L1/L2）保持盲态，不产生向上依赖违规。
    # Epic #1987 追踪中。
    "domain": 3,
    "execution": 3,
    "orchestra": 3,
    "roles": 3,
    "runtime": 3,
    "services": 3,
    # Layer 2 - Command & IO gateway（CLI 命令、HTTP 入口、输出渲染）
    "commands": 2,
    "server": 2,
    "ui": 2,
    # Layer 1 - CLI entry
    # Note: cli.py is a file, not a module directory
}

# Layer allowed dependencies: layer N can import from layers >= N
LAYER_ALLOWED_DEPS: dict[int, set[int]] = {
    1: {1, 2, 3, 4, 5, 6},  # CLI can import everything
    2: {2, 3, 4, 5, 6},  # Command can import layers 2-6
    3: {3, 4, 5, 6},  # Service & Domain can import layers 3-6
    4: {4, 5, 6},  # Execution can import layers 4-6
    5: {5, 6},  # Environment can import layers 5-6
    6: {6},  # Infrastructure can only import layer 6
}


def discover_modules() -> list[str]:
    """Discover all top-level vibe3 submodules.

    Returns:
        List of module names (e.g., ['services', 'domain', 'agents'])
    """
    vibe3_root = Path("src/vibe3")
    if not vibe3_root.exists():
        return []

    modules = []
    for item in vibe3_root.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            modules.append(item.name)
        elif (
            item.is_file()
            and item.suffix == ".py"
            and item.stem not in ["__init__", "__main__"]
        ):
            # Handle single-file modules like cli.py (but not for this test suite)
            pass

    return sorted(modules)


def build_import_graph() -> dict[str, list[str]]:
    """Build import graph from vibe3.analysis.dag_service.

    Aggregates file-level imports to top-level module level.

    Returns:
        Dict mapping module name to list of imported module names
    """
    from vibe3.analysis.dag_service import build_module_graph

    file_graph = build_module_graph()

    # Aggregate to top-level module
    module_imports: dict[str, set[str]] = defaultdict(set)

    for file_module, node in file_graph.items():
        # Extract top-level module from file path
        # e.g., vibe3.services.flow_service -> services
        if not file_module.startswith("vibe3."):
            continue

        parts = file_module.split(".")
        if len(parts) < 2:
            continue

        source_module = parts[1]  # e.g., 'services'

        # Process imports
        for imp in node.imports:
            if not imp.startswith("vibe3."):
                continue

            imp_parts = imp.split(".")
            if len(imp_parts) < 2:
                continue

            target_module = imp_parts[1]  # e.g., 'domain'

            # Skip self-imports
            if target_module != source_module:
                module_imports[source_module].add(target_module)

    # Convert sets to sorted lists
    return {k: sorted(v) for k, v in module_imports.items()}


def extract_file_imports(file_path: str) -> list[str]:
    """Extract vibe3 imports from a Python file.

    Args:
        file_path: Path to Python file

    Returns:
        List of imported module names (full dotted paths)
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
                # Try to identify if importing a submodule or a class/function
                for alias in node.names:
                    full_module = f"{node.module}.{alias.name}"
                    # Heuristic: lowercase first letter suggests submodule
                    if alias.name[0].islower():
                        imports.append(full_module)
                    else:
                        # Likely a class/function, just record the module
                        imports.append(node.module)

    return imports


def get_module_layer(module_name: str) -> int | None:
    """Get the architecture layer for a module.

    Args:
        module_name: Top-level module name (e.g., 'services')

    Returns:
        Layer number (1-6) or None if not in map
    """
    return MODULE_LAYER_MAP.get(module_name)


@pytest.fixture
def module_registry() -> list[str]:
    """Fixture providing list of all vibe3 modules."""
    return discover_modules()


@pytest.fixture
def import_graph() -> dict[str, list[str]]:
    """Fixture providing module import graph."""
    return build_import_graph()


@pytest.fixture
def module_layer_map() -> dict[str, int]:
    """Fixture providing module-to-layer mapping."""
    return MODULE_LAYER_MAP


@pytest.fixture
def layer_allowed_deps() -> dict[int, set[int]]:
    """Fixture providing layer dependency rules."""
    return LAYER_ALLOWED_DEPS
