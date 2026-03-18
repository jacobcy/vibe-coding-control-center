"""Tests for inspection models."""

import pytest

from vibe3.models.inspection import CallNode, CommandInspection


def test_call_node_creation() -> None:
    """Test creating a call node."""
    node = CallNode(name="show", line=84)

    assert node.name == "show"
    assert node.line == 84
    assert node.calls == []


def test_call_node_with_children() -> None:
    """Test call node with child nodes."""
    child1 = CallNode(name="setup_logging", line=95)
    child2 = CallNode(name="trace_context", line=97)

    parent = CallNode(name="show", line=84, calls=[child1, child2])

    assert len(parent.calls) == 2
    assert parent.calls[0].name == "setup_logging"
    assert parent.calls[1].name == "trace_context"


def test_call_node_to_dict() -> None:
    """Test converting call node to dictionary."""
    child = CallNode(name="setup_logging", line=95)
    parent = CallNode(name="show", line=84, calls=[child])

    result = parent.to_dict()

    assert result["name"] == "show"
    assert result["line"] == 84
    assert len(result["calls"]) == 1
    assert result["calls"][0]["name"] == "setup_logging"


def test_command_inspection_creation() -> None:
    """Test creating a command inspection."""
    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=16,
    )

    assert inspection.command == "pr show"
    assert inspection.file == "src/vibe3/commands/pr.py"
    assert inspection.call_depth == 16
    assert inspection.call_tree == []


def test_command_inspection_with_tree() -> None:
    """Test command inspection with call tree."""
    child = CallNode(name="setup_logging", line=95)
    root = CallNode(name="show", line=84, calls=[child])

    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=16,
        call_tree=[root],
    )

    assert len(inspection.call_tree) == 1
    assert inspection.call_tree[0].name == "show"
    assert len(inspection.call_tree[0].calls) == 1


def test_command_inspection_to_yaml() -> None:
    """Test converting command inspection to YAML."""
    root = CallNode(name="show", line=84)
    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=16,
        call_tree=[root],
    )

    yaml_str = inspection.to_yaml()

    assert "command: pr show" in yaml_str
    assert "file: src/vibe3/commands/pr.py" in yaml_str
    assert "call_depth: 16" in yaml_str
    assert "call_tree:" in yaml_str


def test_command_inspection_to_json() -> None:
    """Test converting command inspection to JSON."""
    root = CallNode(name="show", line=84)
    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=16,
        call_tree=[root],
    )

    json_str = inspection.to_json()

    assert '"command": "pr show"' in json_str
    assert '"file": "src/vibe3/commands/pr.py"' in json_str
    assert '"call_depth": 16' in json_str


def test_command_inspection_to_tree() -> None:
    """Test converting command inspection to ASCII tree."""
    child1 = CallNode(name="setup_logging", line=95)
    child2 = CallNode(name="trace_context", line=97)
    root = CallNode(name="show", line=84, calls=[child1, child2])

    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=16,
        call_tree=[root],
    )

    tree_str = inspection.to_tree()

    assert "pr show (src/vibe3/commands/pr.py:84)" in tree_str
    assert "├─ setup_logging (L95)" in tree_str
    assert "└─ trace_context (L97)" in tree_str


def test_command_inspection_to_tree_nested() -> None:
    """Test ASCII tree with nested calls."""
    grandchild1 = CallNode(name="sqlite_client.get_pr", line=125)
    grandchild2 = CallNode(name="git_client.get_current_branch", line=63)
    child = CallNode(
        name="service.get_pr", line=104, calls=[grandchild1, grandchild2]
    )
    root = CallNode(name="show", line=84, calls=[child])

    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=16,
        call_tree=[root],
    )

    tree_str = inspection.to_tree()

    assert "show (L84)" in tree_str
    assert "service.get_pr (L104)" in tree_str
    assert "sqlite_client.get_pr (L125)" in tree_str
    assert "git_client.get_current_branch (L63)" in tree_str


def test_command_inspection_to_mermaid() -> None:
    """Test converting command inspection to Mermaid diagram."""
    child = CallNode(name="setup_logging", line=95)
    root = CallNode(name="show", line=84, calls=[child])

    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=16,
        call_tree=[root],
    )

    mermaid_str = inspection.to_mermaid()

    assert "```mermaid" in mermaid_str
    assert "graph TD" in mermaid_str
    assert '["setup_logging:95"]' in mermaid_str
    assert "graph TD" in mermaid_str


def test_command_inspection_deep_nesting() -> None:
    """Test command inspection with deeply nested call tree."""
    leaf = CallNode(name="logger.debug", line=10)
    branch = CallNode(name="helper_func", line=20, calls=[leaf])
    trunk = CallNode(name="service_method", line=30, calls=[branch])
    root = CallNode(name="show", line=84, calls=[trunk])

    inspection = CommandInspection(
        command="pr show",
        file="src/vibe3/commands/pr.py",
        call_depth=4,
        call_tree=[root],
    )

    # Test YAML
    yaml_str = inspection.to_yaml()
    assert "logger.debug" in yaml_str

    # Test tree
    tree_str = inspection.to_tree()
    assert "show" in tree_str
    assert "service_method" in tree_str
    assert "helper_func" in tree_str
    assert "logger.debug" in tree_str

    # Test Mermaid
    mermaid_str = inspection.to_mermaid()
    assert "graph TD" in mermaid_str