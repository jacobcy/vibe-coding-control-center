"""Test FlowManager import migration across codebase."""

import ast


def test_manager_imports_from_domain():
    """Verify manager.py imports FlowManager from domain."""
    with open("src/vibe3/roles/manager.py") as f:
        tree = ast.parse(f.read())

    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    flow_manager_imports = [
        imp
        for imp in imports
        if imp.module and "FlowManager" in [alias.name for alias in imp.names]
    ]

    assert len(flow_manager_imports) == 1
    assert flow_manager_imports[0].module == "vibe3.domain"


def test_server_registry_imports_from_domain():
    """Verify server/registry.py imports FlowManager from server package."""
    with open("src/vibe3/server/registry.py") as f:
        tree = ast.parse(f.read())

    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    flow_manager_imports = [
        imp
        for imp in imports
        if imp.module and "FlowManager" in [alias.name for alias in imp.names]
    ]

    assert len(flow_manager_imports) == 1
    # After refactor: server/registry.py imports from vibe3.server (re-export)
    assert flow_manager_imports[0].module == "vibe3.server"


def test_governance_sync_runner_imports_from_domain():
    """Verify governance_sync_runner.py imports FlowManager from domain."""
    with open("src/vibe3/execution/governance_sync_runner.py") as f:
        tree = ast.parse(f.read())

    # Find all FlowManager imports in the file
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    flow_manager_imports = [
        imp
        for imp in imports
        if imp.module and "FlowManager" in [alias.name for alias in imp.names]
    ]

    # Should have exactly 2 imports (lines 61 and 177)
    assert len(flow_manager_imports) == 2
    for imp in flow_manager_imports:
        assert imp.module == "vibe3.domain"


def test_mcp_imports_from_domain():
    """Verify mcp.py imports FlowManager from domain."""
    with open("src/vibe3/commands/mcp.py") as f:
        tree = ast.parse(f.read())

    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    flow_manager_imports = [
        imp
        for imp in imports
        if imp.module and "FlowManager" in [alias.name for alias in imp.names]
    ]

    assert len(flow_manager_imports) == 1
    assert flow_manager_imports[0].module == "vibe3.domain"


def test_governance_scan_imports_from_domain():
    """Verify governance_scan.py imports FlowManager from domain."""
    with open("src/vibe3/domain/handlers/governance_scan.py") as f:
        tree = ast.parse(f.read())

    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    flow_manager_imports = [
        imp
        for imp in imports
        if imp.module and "FlowManager" in [alias.name for alias in imp.names]
    ]

    assert len(flow_manager_imports) == 1
    assert flow_manager_imports[0].module == "vibe3.domain"
