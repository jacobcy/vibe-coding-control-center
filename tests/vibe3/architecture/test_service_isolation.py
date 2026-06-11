"""Architecture tests for services submodule isolation.

Phase 5: Establish xfail tracking for cross-module internal imports.

These tests verify that services submodules use only public APIs
when importing from each other, avoiding internal implementation details.
"""

import ast
from pathlib import Path
from typing import Dict, List

# Define submodule public APIs (Phase 4 completed)
PUBLIC_APIS = {
    "services.pr": {
        # Services
        "PRService",
        "PRCreateUsecase",
        "PrReadyUsecase",
        "VerdictService",
        "PRLocCommentService",
        "PRReviewBriefingService",
        # Functions
        "create_pr",
        "analyze_critical_files",
        "build_pr_analysis",
        "calculate_pr_risk_score",
        "filter_critical_files",
        "get_pr_changed_files",
        "get_pr_commit_count",
        "get_recent_commits",
        "resolve_branch_from_pr",
        "resolve_command_branch",
        "generate_score_report",
        # Types
        "PRCreateResult",
        "PRDimensions",
        "RiskLevel",
        "RiskScore",
    },
    "services.issue": {
        "IssueService",
        "IssueCollectionService",
        "IssueFlowService",
        "IssueTitleCacheService",
        "load_issue_info",
        "fail_issue",
    },
    "services.task": {
        "TaskService",
        "TaskResumeUsecase",
        "TaskResumeOperations",
        "TaskStatusBucket",
    },
    "services.orchestra": {
        "OrchestraStatusService",
        "OrchestraSnapshot",
        "IssueStatusEntry",
        "is_running_issue",
    },
    "services.flow": {
        "FlowService",
        "FlowProjectionService",
        "FlowStatusService",
        "FlowRecoveryService",
        "FlowRebuildUsecase",
        "create_flow_manager",
        "classify_flow",
        "get_flow_state",
    },
    "services.shared": {
        "FileLoader",
        "material_loader",
        "policy_loader",
        "SignatureService",
        "LabelService",
        "ErrorTrackingService",
        "LocService",
        "VersionService",
        "ArtifactParser",
    },
}


def find_internal_imports(module_a: str, module_b: str) -> List[Dict]:
    """Find internal imports from module_a to module_b.

    Returns:
        [
            {
                "file": "src/vibe3/services/issue/issue_service.py",
                "line": 42,
                "import": "from vibe3.services.task.internal import TaskHelper",
                "type": "internal_import"
            }
        ]
    """
    violations = []
    module_path = Path("src/vibe3") / module_a.replace(".", "/")

    if not module_path.exists():
        return violations

    for py_file in module_path.rglob("*.py"):
        # Skip __init__.py, __pycache__, and test files
        if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
            continue

        try:
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    # Check if importing from module_b's internal paths
                    if module_b in module and "internal" in module:
                        imported_names = ", ".join(alias.name for alias in node.names)
                        violations.append(
                            {
                                "file": str(py_file),
                                "line": node.lineno,
                                "import": f"from {module} import {imported_names}",
                                "type": "internal_import",
                            }
                        )
        except SyntaxError:
            # Skip files with syntax errors
            continue

    return violations


def test_no_cross_module_internal_imports():
    """Verify no cross-module internal imports.

    Goal: All internal imports count should reach zero.
    Current: Phase 5 establishes baseline.
    """
    violations = []

    modules = list(PUBLIC_APIS.keys())
    for i, module_a in enumerate(modules):
        for module_b in modules[i + 1 :]:
            # Check bidirectional imports
            violations.extend(find_internal_imports(module_a, module_b))
            violations.extend(find_internal_imports(module_b, module_a))

    # Phase 5 goal: establish baseline
    baseline_count = len(violations)
    print(f"\n📊 当前内部引用数量: {baseline_count}")

    # Output detailed violations
    for v in violations[:10]:  # Show first 10
        print(f"  {v['file']}:{v['line']} - {v['import']}")

    if baseline_count > 10:
        print(f"  ... 还有 {baseline_count - 10} 个违规")

    # Phase 5: Record baseline, expect xfail (strict=False)
    assert len(violations) == 0, f"发现 {len(violations)} 处内部引用违规"


def test_imports_via_public_api():
    """Verify cross-module imports use only public APIs.

    Goal: All cross-module imports must come from __init__.py public symbols.
    """
    violations = []

    for module in PUBLIC_APIS:
        module_path = Path("src/vibe3") / module.replace(".", "/")

        if not module_path.exists():
            continue

        for py_file in module_path.rglob("*.py"):
            if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                continue

            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        imported_module = node.module or ""
                        # Check if importing from other modules
                        for other_module, symbols in PUBLIC_APIS.items():
                            if other_module != module and (
                                imported_module == other_module
                                or imported_module.startswith(other_module + ".")
                            ):
                                # Verify imported symbols are in public list
                                for alias in node.names:
                                    if alias.name not in symbols:
                                        violations.append(
                                            {
                                                "file": str(py_file),
                                                "line": node.lineno,
                                                "import": (
                                                    f"from {imported_module} "
                                                    f"import {alias.name}"
                                                ),
                                                "expected": (
                                                    f"应从 {other_module} "
                                                    f"的公开 API 导入"
                                                ),
                                            }
                                        )
            except SyntaxError:
                continue

    print(f"\n📊 非公开 API 导入数量: {len(violations)}")
    for v in violations[:10]:
        print(f"  {v['file']}:{v['line']} - {v['import']}")
        print(f"    {v['expected']}")

    # Phase 5: Record baseline, expect xfail (strict=False)
    assert len(violations) == 0
