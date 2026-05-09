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
    # Setup mocks
    mock_resolve_root.return_value = tmp_path

    # Create supervisor file
    supervisor_dir = tmp_path / "supervisor"
    supervisor_dir.mkdir()
    supervisor_file = supervisor_dir / "project-explorer.md"
    supervisor_file.write_text("# Test Supervisor\n\nAnswer questions.")

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
    assert call_args.kwargs["options"].agent == "vibe-reviewer"
    assert call_args.kwargs["options"].timeout_seconds == 180


@patch("vibe3.server.mcp.resolve_orchestra_repo_root")
def test_orchestra_ask_handles_missing_supervisor_file(mock_resolve_root, tmp_path):
    """Test that orchestra_ask handles missing supervisor file gracefully."""
    mock_resolve_root.return_value = tmp_path

    # Don't create supervisor file

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
    assert "Supervisor file not found" in result_data["error"]


@patch("vibe3.server.mcp.CodeagentBackend")
@patch("vibe3.server.mcp.resolve_orchestra_repo_root")
def test_orchestra_ask_handles_agent_failure(
    mock_resolve_root, mock_backend_class, tmp_path
):
    """Test that orchestra_ask handles agent execution failure gracefully."""
    mock_resolve_root.return_value = tmp_path

    # Create supervisor file
    supervisor_dir = tmp_path / "supervisor"
    supervisor_dir.mkdir()
    supervisor_file = supervisor_dir / "project-explorer.md"
    supervisor_file.write_text("# Test Supervisor")

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
