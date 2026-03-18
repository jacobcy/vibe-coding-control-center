"""Tests for command analyzer call tree building."""

import pytest

from vibe3.services.command_analyzer import (
    _calculate_max_depth,
    should_expand,
)


def test_should_expand_service_calls() -> None:
    """Test that service calls should be expanded."""
    assert should_expand("service.get_pr") is True
    assert should_expand("service.create_draft") is True


def test_should_expand_client_calls() -> None:
    """Test that client calls should be expanded."""
    assert should_expand("client.get_current_branch") is True
    assert should_expand("github_client.get_pr") is True


def test_should_not_expand_builtin() -> None:
    """Test that builtin calls should not be expanded."""
    assert should_expand("logger.info") is False
    assert should_expand("print") is False
    assert should_expand("len") is False
    assert should_expand("str") is False
    assert should_expand("typer.echo") is False


def test_should_not_expand_json_yaml() -> None:
    """Test that json/yaml calls should not be expanded."""
    assert should_expand("json.dumps") is False
    assert should_expand("yaml.dump") is False


def test_calculate_max_depth_empty() -> None:
    """Test max depth calculation with empty list."""
    from vibe3.models.inspection import CallNode

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
    leaf2 = CallNode(name="leaf2", line=40)
    branch1 = CallNode(name="branch1", line=20, calls=[leaf1])
    branch2 = CallNode(name="branch2", line=25)  # No children
    root = CallNode(name="root", line=10, calls=[branch1, branch2])

    depth = _calculate_max_depth([root])
    assert depth == 3  # root -> branch1 -> leaf1