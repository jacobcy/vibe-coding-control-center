"""MCP server commands."""

import typer

from vibe3.server import create_mcp_server

app = typer.Typer(
    help="MCP server for Orchestra tools",
    no_args_is_help=True,
)


@app.command()
def run() -> None:
    """Run MCP server in stdio mode (for MCP client integration).

    This runs the Orchestra MCP server using stdio transport, which is
    compatible with Claude Code's MCP client configuration.

    Example usage in .claude/settings.json:
        "mcpServers": {
          "orchestra": {
            "command": "uv",
            "args": ["run", "python", "src/vibe3/cli.py", "mcp", "run"]
          }
        }

    Available MCP tools:
      - orchestra_status: Get current orchestra system status
      - orchestra_issue_detail: Get detailed info about a specific issue
      - orchestra_dispatch_history: View recent dispatch execution history

    MCP resources:
      - orchestra://status: Current status as JSON
      - orchestra://issues: List of managed issues
      - orchestra://circuit-breaker: Circuit breaker state
    """
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.config.orchestra_settings import load_orchestra_config
    from vibe3.domain import FlowManager
    from vibe3.services import OrchestraStatusService

    config = load_orchestra_config()

    # Create dependencies for MCP server
    github = GitHubClient()
    store = SQLiteClient()
    git_client = GitClient()

    # Use FlowManager as the FlowReader implementation
    # (it implements the FlowReader protocol)
    orchestrator = FlowManager(config, store=store, git=git_client, github=github)

    # Create status service
    status_service = OrchestraStatusService(
        config,
        github=github,
        orchestrator=orchestrator,
        circuit_breaker=None,
        failed_gate=None,
        git_client=git_client,
    )

    # Create and run MCP server
    mcp = create_mcp_server(status_service, get_queued=None)

    # Run in stdio mode (standard MCP client transport)
    mcp.run(transport="stdio")
