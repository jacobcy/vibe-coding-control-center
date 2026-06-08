"""Test FlowManager import migration across codebase."""

import ast


def test_manager_uses_flow_factory():
    """Verify manager.py uses flow_factory instead of importing FlowManager.

    After circular dependency fix (issue #2001), manager.py uses
    create_flow_manager from services.flow_factory instead of directly
    importing FlowManager from vibe3.domain.
    """
    with open("src/vibe3/roles/manager.py") as f:
        content = f.read()

    # Should NOT import FlowManager from domain
    assert "from vibe3.domain import FlowManager" not in content

    # Should use create_flow_manager via services public API
    assert "from vibe3.services import create_flow_manager" in content


def test_server_registry_imports_from_domain():
    """Verify server/registry.py imports FlowManager directly from domain."""
    with open("src/vibe3/server/registry.py") as f:
        tree = ast.parse(f.read())

    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    flow_manager_imports = [
        imp
        for imp in imports
        if imp.module and "FlowManager" in [alias.name for alias in imp.names]
    ]

    assert len(flow_manager_imports) == 1
    # After circular dependency elimination: server/registry.py imports
    # directly from vibe3.domain
    assert flow_manager_imports[0].module == "vibe3.domain"


def test_governance_sync_runner_does_not_import_flow_manager():
    """Verify governance_sync_runner.py does NOT import FlowManager from domain.

    After circular dependency fix (issue #2001), governance_sync_runner.py
    uses OrchestraStatusService.create() factory method instead of directly
    importing FlowManager from vibe3.domain.
    """
    with open("src/vibe3/execution/governance_sync_runner.py") as f:
        content = f.read()

    # Should NOT have any FlowManager imports
    assert "from vibe3.domain import FlowManager" not in content

    # Should use OrchestraStatusService.create() instead
    assert "OrchestraStatusService.create(" in content


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
