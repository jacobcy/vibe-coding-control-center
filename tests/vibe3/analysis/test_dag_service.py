"""DAGService 单元测试."""

import tempfile
from pathlib import Path

import pytest

from vibe3.analysis.dag_service import (
    DAGError,
    ModuleNode,
    _extract_imports,
    build_module_graph,
    expand_impacted_modules,
)

# 预构建的测试图
MOCK_GRAPH: dict[str, ModuleNode] = {
    "vibe3.services.flow_service": ModuleNode(
        module="vibe3.services.flow_service",
        file_path="src/vibe3/services/flow_service.py",
        imports=["vibe3.clients.git_client"],
    ),
    "vibe3.commands.flow": ModuleNode(
        module="vibe3.commands.flow",
        file_path="src/vibe3/commands/flow.py",
        imports=["vibe3.services.flow_service", "vibe3.clients.git_client"],
    ),
    "vibe3.clients.git_client": ModuleNode(
        module="vibe3.clients.git_client",
        file_path="src/vibe3/clients/git_client.py",
        imports=[],
    ),
}


class TestBuildModuleGraph:
    """build_module_graph 测试."""

    def test_raises_when_root_missing(self) -> None:
        with pytest.raises(DAGError, match="not found"):
            build_module_graph("/nonexistent/path")

    def test_builds_graph_from_real_src(self) -> None:
        # 使用真实 src/vibe3 目录
        graph = build_module_graph("src/vibe3")
        assert len(graph) > 0
        # 所有节点都有 module 字段
        for module, node in graph.items():
            assert node.module == module


class TestExpandImpactedModules:
    """expand_impacted_modules 测试."""

    def test_seed_always_in_impacted(self) -> None:
        result = expand_impacted_modules(
            seed_files=["src/vibe3/clients/git_client.py"],
            graph=MOCK_GRAPH,
        )
        assert "vibe3.clients.git_client" in result.impacted_modules

    def test_upstream_modules_included(self) -> None:
        # git_client 被 flow_service 和 commands.flow 依赖
        result = expand_impacted_modules(
            seed_files=["src/vibe3/clients/git_client.py"],
            graph=MOCK_GRAPH,
        )
        assert "vibe3.services.flow_service" in result.impacted_modules
        assert "vibe3.commands.flow" in result.impacted_modules

    def test_non_python_files_ignored(self) -> None:
        result = expand_impacted_modules(
            seed_files=["bin/vibe", "lib/flow.sh"],
            graph=MOCK_GRAPH,
        )
        assert result.seed_modules == []
        assert result.impacted_modules == []

    def test_empty_seeds(self) -> None:
        result = expand_impacted_modules(seed_files=[], graph=MOCK_GRAPH)
        assert result.seed_modules == []
        assert result.impacted_modules == []


class TestExtractImports:
    """_extract_imports 测试."""

    def test_deduplicates_multiple_imports_from_same_module(self) -> None:
        """验证 `from ... import A, B, C` 不会产生重复模块名."""
        # 创建临时 Python 文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from vibe3.clients import GitClient, GitHubClient, SQLiteClient\n")
            temp_file = f.name

        try:
            # 调用 _extract_imports
            imports = _extract_imports(temp_file)

            # 验证：应该只有一条 vibe3.clients 记录
            assert imports == ["vibe3.clients"]
        finally:
            # 清理临时文件
            Path(temp_file).unlink()
