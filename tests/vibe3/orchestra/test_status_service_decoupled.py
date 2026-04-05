"""Verify OrchestraStatusService does not depend on FlowManager at import time."""

import importlib
import sys


def test_status_service_does_not_import_flow_manager():
    """status_service 模块不应在顶层 import FlowManager。"""
    # 清除缓存以强制重新导入
    for key in list(sys.modules.keys()):
        if "status_service" in key or "flow_manager" in key:
            del sys.modules[key]

    import vibe3.orchestra.services.status_service as mod

    source = importlib.util.find_spec(mod.__name__)
    assert source is not None
    # FlowManager 不应出现在模块级 import（懒加载也应消失）
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(mod.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                assert "flow_manager" not in (
                    name or ""
                ), f"status_service should not import flow_manager, found: {name}"
