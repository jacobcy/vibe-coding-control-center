"""Tests for config public API type-checking exports."""

from __future__ import annotations

import ast
from pathlib import Path


def test_config_lazy_exports_have_type_checking_bindings() -> None:
    """Every config lazy export should have a TYPE_CHECKING binding.

    Runtime ``__getattr__`` exports are not enough for mypy. If ``__all__`` and
    ``_SYMBOL_MODULES`` expose a name, the ``TYPE_CHECKING`` branch must import
    the same name so type annotations can resolve to real objects.
    """
    init_path = Path("src/vibe3/config/__init__.py")
    tree = ast.parse(init_path.read_text(encoding="utf-8"))

    public_exports: set[str] = set()
    lazy_exports: set[str] = set()
    type_checking_imports: set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == "__all__"
                and isinstance(node.value, ast.List)
            ):
                public_exports = {
                    item.value
                    for item in node.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }
            if (
                isinstance(target, ast.Name)
                and target.id == "_SYMBOL_MODULES"
                and isinstance(node.value, ast.Dict)
            ):
                lazy_exports = {
                    item.value
                    for item in node.value.keys
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if not isinstance(node.test, ast.Name) or node.test.id != "TYPE_CHECKING":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.ImportFrom):
                type_checking_imports.update(
                    alias.asname or alias.name for alias in child.names
                )

    missing = sorted((public_exports | lazy_exports) - type_checking_imports)

    assert (
        missing == []
    ), "Config lazy exports missing TYPE_CHECKING bindings: " + ", ".join(missing)
