"""Shared fixtures for modularity validation tests."""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

# Import taxonomy for fixture
from vibe3.runtime.taxonomy import MODULE_CATEGORY_MAP, ModuleCategory

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
    """Build a test-only top-level import graph from repository source.

    Returns:
        Dict mapping module name to list of imported module names
    """
    module_imports: dict[str, set[str]] = defaultdict(set)
    source_root = Path("src/vibe3")
    for source_file in sorted(source_root.rglob("*.py")):
        relative = source_file.relative_to("src").with_suffix("")
        file_module = ".".join(relative.parts)
        if not file_module.startswith("vibe3."):
            continue
        parts = file_module.split(".")
        if len(parts) < 2:
            continue
        source_module = parts[1]
        for imp in extract_file_imports(str(source_file)):
            if not imp.startswith("vibe3."):
                continue
            imp_parts = imp.split(".")
            if len(imp_parts) < 2:
                continue
            target_module = imp_parts[1]
            if target_module != source_module:
                module_imports[source_module].add(target_module)
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


@dataclass
class CrossModuleImport:
    """Represents a cross-module import statement.

    Attributes:
        source_file: Path to the file containing the import
        target_module: The top-level module being imported from (e.g., 'services')
        import_path: Full import path (e.g., 'vibe3.services.flow_service')
        symbols: List of symbols being imported
        is_deep: True if importing from a submodule (bypassing __init__.py)
    """

    source_file: str
    target_module: str
    import_path: str
    symbols: list[str]
    is_deep: bool


def get_module_public_api(module_name: str) -> set[str]:
    """Extract public API symbols from module's __init__.py.

    AST parses the __all__ definition to get the list of exported symbols.

    Args:
        module_name: Top-level module name (e.g., 'services')

    Returns:
        Set of symbol names in __all__, or empty set if __all__ not found
    """
    init_path = Path("src/vibe3", *module_name.split("."), "__init__.py")
    if not init_path.exists():
        return set()

    try:
        source = init_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return set()

    # Extract __all__ list
    for node in ast.walk(tree):
        # Check for regular assignment: __all__ = [...]
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.List):
                        symbols = set()
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                symbols.add(elt.value)
                        return symbols
        # Check for annotated assignment: __all__: list[str] = [...]
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                if isinstance(node.value, ast.List):
                    symbols = set()
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant):
                            symbols.add(elt.value)
                    return symbols

    return set()


def _resolve_public_import_target(parts: list[str]) -> tuple[str, bool]:
    """Resolve the public API target and whether an import bypasses it."""
    target_module = parts[1]

    if target_module == "services" and len(parts) >= 3:
        subpackage = parts[2]
        subpackage_init = Path("src/vibe3/services") / subpackage / "__init__.py"
        if subpackage_init.exists():
            public_target = f"services.{subpackage}"
            return public_target, len(parts) > 3

    return target_module, len(parts) > 2


def extract_cross_module_imports(source_module: str) -> list[CrossModuleImport]:
    """Extract all cross-module imports from a source module.

    Scans all .py files in the module directory and extracts import statements
    that reference other vibe3 modules.

    Args:
        source_module: Top-level module name (e.g., 'services')

    Returns:
        List of CrossModuleImport instances for cross-module imports only
    """
    module_dir = Path(f"src/vibe3/{source_module}")
    if not module_dir.exists():
        return []

    imports: list[CrossModuleImport] = []

    # Recursively find all .py files in the module
    for py_file in module_dir.rglob("*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        # Extract imports from AST
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if not node.module:
                    continue

                # Only process vibe3 imports
                if not node.module.startswith("vibe3."):
                    continue

                # Parse the import path
                parts = node.module.split(".")
                if len(parts) < 2:
                    continue

                target_module, is_deep = _resolve_public_import_target(parts)
                source_top_module = source_module.split(".", maxsplit=1)[0]
                target_top_module = target_module.split(".", maxsplit=1)[0]

                # Skip same-module imports
                if target_top_module == source_top_module:
                    continue

                # Extract imported symbols
                symbols = [alias.name for alias in node.names]

                imports.append(
                    CrossModuleImport(
                        source_file=str(py_file),
                        target_module=target_module,
                        import_path=node.module,
                        symbols=symbols,
                        is_deep=is_deep,
                    )
                )

    return imports


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


@pytest.fixture
def module_public_api(module_registry: list[str]) -> dict[str, set[str]]:
    """Fixture providing public API symbols for each module.

    Returns:
        Dict mapping module name to set of symbols in __all__
    """
    public_api = {
        module_name: get_module_public_api(module_name)
        for module_name in module_registry
    }

    services_dir = Path("src/vibe3/services")
    if services_dir.exists():
        for item in services_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                public_api[f"services.{item.name}"] = get_module_public_api(
                    f"services.{item.name}"
                )

    return public_api


@pytest.fixture
def module_category_map() -> dict[str, ModuleCategory]:
    """Fixture providing module-to-category mapping."""
    return MODULE_CATEGORY_MAP
