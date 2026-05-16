"""Tests for orchestra_ask MCP tool."""

import json
from unittest.mock import MagicMock, patch

from vibe3.server.mcp import create_mcp_server


def test_orchestra_ask_tool_registered():
    """Test that orchestra_ask tool is registered in MCP server."""
    mock_status_service = MagicMock()
    mcp = create_mcp_server(mock_status_service)

    # Get list of registered tools
    tools = [tool.name for tool in mcp._tool_manager._tools.values()]

    assert "orchestra_ask" in tools, "orchestra_ask tool should be registered"


@patch("vibe3.server.mcp.CodeagentBackend")
@patch("vibe3.server.mcp.resolve_orchestra_repo_root")
def test_orchestra_ask_returns_answer(mock_resolve_root, mock_backend_class, tmp_path):
    """Test that orchestra_ask returns answer from sub-agent."""
    mock_resolve_root.return_value = tmp_path

    # Mock backend result
    mock_backend = MagicMock()
    mock_result = MagicMock()
    mock_result.stdout = "This is the answer from the agent."
    mock_backend.run.return_value = mock_result
    mock_backend_class.return_value = mock_backend

    # Create MCP server and call tool
    mock_status_service = MagicMock()
    mcp = create_mcp_server(mock_status_service)

    # Get the orchestra_ask tool function
    orchestra_ask = None
    for tool in mcp._tool_manager._tools.values():
        if tool.name == "orchestra_ask":
            orchestra_ask = tool.fn
            break

    assert orchestra_ask is not None

    # Call the tool
    result = orchestra_ask("What is the structure of src/vibe3/?")

    # Verify result
    assert result == "This is the answer from the agent."

    # Verify backend was called correctly
    mock_backend.run.assert_called_once()
    call_args = mock_backend.run.call_args
    assert call_args.kwargs["cwd"] == tmp_path
    assert call_args.kwargs["role"] == "explorer"
    assert call_args.kwargs["options"].backend == "claude"
    assert call_args.kwargs["options"].model == "sonnet"
    assert call_args.kwargs["options"].timeout_seconds == 180
    assert call_args.kwargs["include_global_notice"] is False
    assert call_args.kwargs["task"] == "What is the structure of src/vibe3/?"


@patch("vibe3.server.mcp.CodeagentBackend")
@patch("vibe3.server.mcp.resolve_orchestra_repo_root")
def test_orchestra_ask_handles_agent_failure(
    mock_resolve_root, mock_backend_class, tmp_path
):
    """Test that orchestra_ask handles agent execution failure gracefully."""
    mock_resolve_root.return_value = tmp_path

    # Mock backend to raise exception
    mock_backend = MagicMock()
    mock_backend.run.side_effect = Exception("Agent execution failed")
    mock_backend_class.return_value = mock_backend

    mock_status_service = MagicMock()
    mcp = create_mcp_server(mock_status_service)

    # Get the orchestra_ask tool function
    orchestra_ask = None
    for tool in mcp._tool_manager._tools.values():
        if tool.name == "orchestra_ask":
            orchestra_ask = tool.fn
            break

    # Call the tool
    result = orchestra_ask("Test question?")

    # Should return error JSON
    result_data = json.loads(result)
    assert "error" in result_data
    assert "Failed to answer question" in result_data["error"]
