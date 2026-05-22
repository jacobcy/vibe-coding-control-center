"""Tests for command analyzer call tree building."""

import pytest

from vibe3.analysis.command_analyzer import (
    _calculate_max_depth,
    should_expand,
)


@pytest.mark.parametrize(
    "call_name,expected",
    [
        # Service calls - should expand
        pytest.param("service.get_pr", True, id="service_call"),
        pytest.param("service.create_draft", True, id="service_call_2"),
        # Client calls - should expand
        pytest.param("client.get_current_branch", True, id="client_call"),
        pytest.param("github_client.get_pr", True, id="github_client_call"),
        # Builtin calls - should not expand
        pytest.param("logger.info", False, id="logger"),
        pytest.param("print", False, id="print"),
        pytest.param("len", False, id="len"),
        pytest.param("str", False, id="str"),
        pytest.param("typer.echo", False, id="typer_echo"),
        # JSON/YAML calls - should not expand
        pytest.param("json.dumps", False, id="json_dumps"),
        pytest.param("yaml.dump", False, id="yaml_dump"),
    ],
)
def test_should_expand(call_name: str, expected: bool) -> None:
    """Test should_expand with various call patterns."""
    assert should_expand(call_name) is expected


def test_calculate_max_depth_empty() -> None:
    """Test max depth calculation with empty list."""

    depth = _calculate_max_depth([])
    assert depth == 0


def test_calculate_max_depth_single_node() -> None:
    """Test max depth with single node."""
    from vibe3.models.inspection import CallNode

    node = CallNode(name="test", line=10)
    depth = _calculate_max_depth([node])
    assert depth == 1


def test_calculate_max_depth_nested() -> None:
    """Test max depth with nested calls."""
    from vibe3.models.inspection import CallNode

    # Create nested structure: root -> child -> grandchild
    grandchild = CallNode(name="grandchild", line=30)
    child = CallNode(name="child", line=20, calls=[grandchild])
    root = CallNode(name="root", line=10, calls=[child])

    depth = _calculate_max_depth([root])
    assert depth == 3


def test_calculate_max_depth_multiple_branches() -> None:
    """Test max depth with multiple branches."""
    from vibe3.models.inspection import CallNode

    # Create structure with different depths
    leaf1 = CallNode(name="leaf1", line=30)
    CallNode(name="leaf2", line=40)
    branch1 = CallNode(name="branch1", line=20, calls=[leaf1])
    branch2 = CallNode(name="branch2", line=25)  # No children
    root = CallNode(name="root", line=10, calls=[branch1, branch2])

    depth = _calculate_max_depth([root])
    assert depth == 3  # root -> branch1 -> leaf1
