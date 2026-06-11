"""Validation test: domain layer architecture independence.

Ensures domain layer does not depend on orchestra layer implementation,
with limited exceptions for infrastructure services (logging).
"""

from __future__ import annotations

import ast
from pathlib import Path


def get_imports_from_file(filepath: Path) -> list[str]:
    """Extract all imports from a Python file.

    Returns:
        List of import strings (e.g., "vibe3.orchestra.flow_dispatch")
    """
    try:
        content = filepath.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return imports


def is_orchestra_import(import_str: str, file_path: Path | None = None) -> bool:
    """Check if an import is from orchestra layer.

    Allowed imports (infrastructure exceptions):
    - orchestra.protocols (TYPE_CHECKING only)
    - orchestra.failed_gate (TYPE_CHECKING only)

    Disallowed:
    - orchestra.flow_dispatch
    - orchestra.global_dispatch_coordinator
    - orchestra.dispatch_health_check
    - orchestra.issue_loader
    - orchestra.queue_operations
    - orchestra.queue_persistence_service
    - Other orchestra modules

    Note: protocols and failed_gate are allowed but must be in TYPE_CHECKING blocks.
    The caller is responsible for checking TYPE_CHECKING context.
    """
    if not import_str.startswith("vibe3.orchestra"):
        return False

    return True


def is_allowed_type_checking_import(
    import_str: str, filepath: Path, node: ast.AST
) -> bool:
    """Return True for the narrow TYPE_CHECKING-only orchestra exceptions."""
    allowed_orchestra_modules = {
        "vibe3.orchestra.protocols",
        "vibe3.orchestra.failed_gate",
    }
    return import_str in allowed_orchestra_modules and is_in_type_checking_block(
        filepath, node
    )


def is_in_type_checking_block(filepath: Path, node: ast.AST) -> bool:
    """Check if a node is inside a TYPE_CHECKING block.

    Args:
        filepath: Path to Python file
        node: AST node to check

    Returns:
        True if node is inside TYPE_CHECKING block
    """
    content = filepath.read_text()
    tree = ast.parse(content)

    # Find TYPE_CHECKING block
    for top_node in ast.walk(tree):
        if isinstance(top_node, ast.If):
            # Check if this is "if TYPE_CHECKING:"
            if (
                isinstance(top_node.test, ast.Name)
                and top_node.test.id == "TYPE_CHECKING"
            ):
                # Check if our node is in this block
                for child in ast.walk(top_node):
                    if child is node:
                        return True

    return False


def test_domain_layer_no_orchestra_imports():
    """Verify domain layer does not import from orchestra (with exceptions)."""
    domain_dir = Path("src/vibe3/domain")

    # Domain files allowed to re-export from orchestra (thin wrapper files
    # that provide backward-compatible access to canonical KERNEL definitions
    # in orchestra/domain_types.py).  These files contain ONLY re-exports.
    _reexport_wrappers = {
        "failed_gate.py",  # re-exports GateResult, GateStatus
        "runtime_protocols.py",  # re-exports ServiceBase
    }

    violations = []

    for py_file in domain_dir.rglob("*.py"):
        # Skip __init__.py (may re-export for backward compatibility)
        if py_file.name == "__init__.py":
            continue

        # Skip re-export wrapper files that back KERNEL definitions
        if py_file.name in _reexport_wrappers:
            continue

        try:
            content = py_file.read_text()
            tree = ast.parse(content)
        except Exception:
            continue

        # Check all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if is_orchestra_import(alias.name, py_file) and not (
                        is_allowed_type_checking_import(alias.name, py_file, node)
                    ):
                        violations.append(
                            f"{py_file.relative_to(domain_dir.parent)}: "
                            f"import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if (
                    node.module
                    and is_orchestra_import(node.module, py_file)
                    and not (
                        is_allowed_type_checking_import(node.module, py_file, node)
                    )
                ):
                    violations.append(
                        f"{py_file.relative_to(domain_dir.parent)}: "
                        f"from {node.module} import ..."
                    )

    if violations:
        violation_list = "\n".join(violations)
        assert False, (
            f"Found {len(violations)} orchestra imports in domain layer:\n"
            f"{violation_list}\n\n"
            "Domain layer should not import from orchestra layer.\n"
            "Allowed exceptions: orchestra.protocols/failed_gate (TYPE_CHECKING only); "
            "failed_gate.py / runtime_protocols.py (re-export wrappers)."
        )

    print(f"✓ Verified {len(list(domain_dir.rglob('*.py')))} domain files")


def test_domain_protocols_use_correct_module():
    """Verify domain modules import protocols from domain.protocols."""
    domain_dir = Path("src/vibe3/domain")

    violations = []

    for py_file in domain_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        try:
            content = py_file.read_text()
        except Exception:
            continue

        # Check if file imports FlowManagerProtocol or FailedGate
        if "FlowManagerProtocol" in content or "FailedGate" in content:
            # Should import from domain.protocols or domain.failed_gate
            if (
                "from vibe3.domain.protocols" not in content
                and "from vibe3.domain.failed_gate" not in content
            ):
                # Check if it's in TYPE_CHECKING block (allowed for orchestra.protocols)
                if "from vibe3.orchestra.protocols" in content:
                    # Verify it's in TYPE_CHECKING
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom):
                            if node.module == "vibe3.orchestra.protocols":
                                if not is_in_type_checking_block(py_file, node):
                                    violations.append(
                                        f"{py_file.relative_to(domain_dir.parent)}: "
                                        "imports FlowManagerProtocol from orchestra "
                                        "(should use domain.protocols or TYPE_CHECKING)"
                                    )

    if violations:
        violation_list = "\n".join(violations)
        assert False, (
            f"Found protocol import violations:\n"
            f"{violation_list}\n\n"
            "Domain modules should import protocols from domain.protocols, "
            "or use TYPE_CHECKING for orchestra.protocols imports."
        )

    print("✓ Verified domain modules use correct protocol imports")


if __name__ == "__main__":
    test_domain_layer_no_orchestra_imports()
    test_domain_protocols_use_correct_module()
    print("\nAll tests passed!")
