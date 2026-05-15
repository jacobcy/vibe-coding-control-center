"""MCP Server for Orchestra - exposes orchestra state to external AI agents."""

import json
import re
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.models.review_runner import AgentOptions
from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.models import PromptRecipe, PromptVariableSource, VariableSourceKind

# Maximum allowed length for orchestra_ask questions
MAX_QUESTION_LENGTH = 500

# Forbidden instruction patterns (case-insensitive) - only clear malicious commands
FORBIDDEN_PATTERNS = [
    "ignore all previous",
    "ignore all instructions",
    "execute:",
    "rm -rf",
]

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from vibe3.services.orchestra_status_service import (
        OrchestraSnapshot,
        OrchestraStatusService,
    )


def _serialize_snapshot(snapshot: "OrchestraSnapshot") -> dict:
    """Convert OrchestraSnapshot to JSON-serializable dict."""
    return {
        "timestamp": snapshot.timestamp,
        "server_running": snapshot.server_running,
        "active_flows": snapshot.active_flows,
        "active_worktrees": snapshot.active_worktrees,
        "queued_issues": list(snapshot.queued_issues),
        "circuit_breaker_state": snapshot.circuit_breaker_state,
        "circuit_breaker_failures": snapshot.circuit_breaker_failures,
        "circuit_breaker_last_failure": snapshot.circuit_breaker_last_failure,
        "active_issues": [
            {
                "number": entry.number,
                "title": entry.title,
                "state": entry.state.value if entry.state else None,
                "assignee": entry.assignee,
                "has_flow": entry.has_flow,
                "flow_branch": entry.flow_branch,
                "has_worktree": entry.has_worktree,
                "worktree_path": entry.worktree_path,
                "has_pr": entry.has_pr,
                "pr_number": entry.pr_number,
                "blocked_by": list(entry.blocked_by),
                # Queue metadata
                "milestone": entry.milestone,
                "roadmap": entry.roadmap,
                "priority": entry.priority,
                "queue_rank": entry.queue_rank,
            }
            for entry in snapshot.active_issues
        ],
    }


def format_snapshot_for_mcp(snapshot: "OrchestraSnapshot") -> str:
    """Format snapshot for MCP tool output."""
    lines = [
        f"## Orchestra Status (timestamp: {snapshot.timestamp:.0f})",
        "",
        f"- **Server**: {'Running' if snapshot.server_running else 'Stopped'}",
        f"- **Active Flows**: {snapshot.active_flows}",
        f"- **Active Worktrees**: {snapshot.active_worktrees}",
        f"- **Queued Issues**: {len(snapshot.queued_issues)}",
        f"- **Circuit Breaker**: {snapshot.circuit_breaker_state}",
        f"  - Failures: {snapshot.circuit_breaker_failures}",
        "",
        "### Active Issues",
        "",
    ]

    for entry in snapshot.active_issues:
        state_str = entry.state.value if entry.state else "unknown"
        lines.append(f"- **#{entry.number}**: {entry.title}")
        lines.append(f"  - State: `{state_str}`")

        # Show queue metadata for READY issues
        if (
            entry.state
            and entry.state.value == "ready"
            and entry.queue_rank is not None
        ):
            queue_info = f"  - Queue Rank: #{entry.queue_rank}"
            if entry.milestone:
                queue_info += f" | milestone={entry.milestone}"
            if entry.roadmap:
                queue_info += f" | roadmap/{entry.roadmap}"
            queue_info += f" | priority/{entry.priority}"
            lines.append(queue_info)

        if entry.assignee:
            lines.append(f"  - Assignee: {entry.assignee}")
        if entry.has_pr and entry.pr_number:
            lines.append(f"  - PR: #{entry.pr_number}")
        if entry.blocked_by:
            blocked_str = ", ".join(f"#{n}" for n in entry.blocked_by)
            lines.append(f"  - Blocked by: {blocked_str}")
        lines.append("")

    return "\n".join(lines)


def _sanitize_output(stdout: str) -> str:
    """Sanitize stdout to redact sensitive information.

    Applies regex-based redaction for:
    - api_key patterns
    - token patterns
    - password patterns

    Args:
        stdout: Raw stdout string from sub-agent

    Returns:
        Sanitized string with sensitive patterns replaced by [REDACTED]
    """
    # Match key/value pairs where the value may contain any non-whitespace
    # characters (covers punctuation, base64, JWT-style tokens, etc.)
    patterns = [
        (r'api[_-]?key["\s]*[:=]["\s]*\S+', "[REDACTED]"),
        (r'token["\s]*[:=]["\s]*\S+', "[REDACTED]"),
        (r'password["\s]*[:=]["\s]*\S+', "[REDACTED]"),
    ]

    sanitized = stdout
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def create_mcp_server(
    status_service: "OrchestraStatusService",
    get_queued: "Callable[[], set[int]] | None" = None,
) -> "FastMCP":
    """Create MCP server for Orchestra.

    Args:
        status_service: OrchestraStatusService instance
        get_queued: Optional callable returning a set of queued issue numbers

    Returns:
        FastMCP server instance

    Raises:
        ImportError: If mcp package is not installed
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp"
        ) from exc

    mcp = FastMCP("orchestra")

    @mcp.resource("orchestra://status")
    def get_status_resource() -> str:
        """Get current orchestra status as JSON."""
        queued = get_queued() if get_queued else None
        snapshot = status_service.snapshot(queued=queued)
        return json.dumps(_serialize_snapshot(snapshot), indent=2)

    @mcp.resource("orchestra://issues")
    def get_issues_resource() -> str:
        """Get list of managed issues with their states."""
        queued = get_queued() if get_queued else None
        snapshot = status_service.snapshot(queued=queued)
        issues_data = [
            {
                "number": entry.number,
                "title": entry.title,
                "state": entry.state.value if entry.state else None,
                "assignee": entry.assignee,
                "has_flow": entry.has_flow,
                "has_pr": entry.has_pr,
                "pr_number": entry.pr_number,
                "blocked_by": list(entry.blocked_by),
            }
            for entry in snapshot.active_issues
        ]
        return json.dumps(issues_data, indent=2)

    @mcp.resource("orchestra://circuit-breaker")
    def get_circuit_breaker_resource() -> str:
        """Get circuit breaker state."""
        queued = get_queued() if get_queued else None
        snapshot = status_service.snapshot(queued=queued)
        cb_data = {
            "state": snapshot.circuit_breaker_state,
            "failures": snapshot.circuit_breaker_failures,
            "last_failure": snapshot.circuit_breaker_last_failure,
        }
        return json.dumps(cb_data, indent=2)

    @mcp.tool()
    def orchestra_status() -> str:
        """Get current orchestra system status.

        Returns a formatted summary of the orchestra system including:
        - Server status
        - Active flows and worktrees
        - Circuit breaker state
        - Active issues with their states
        """
        queued = get_queued() if get_queued else None
        snapshot = status_service.snapshot(queued=queued)
        return format_snapshot_for_mcp(snapshot)

    @mcp.tool()
    def orchestra_issue_detail(issue_number: int) -> str:
        """Get detailed information about a specific issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            JSON-formatted issue details including flow, worktree, and PR status
        """
        queued = get_queued() if get_queued else None
        snapshot = status_service.snapshot(queued=queued)
        for entry in snapshot.active_issues:
            if entry.number == issue_number:
                return json.dumps(
                    {
                        "number": entry.number,
                        "title": entry.title,
                        "state": entry.state.value if entry.state else None,
                        "assignee": entry.assignee,
                        "has_flow": entry.has_flow,
                        "flow_branch": entry.flow_branch,
                        "has_worktree": entry.has_worktree,
                        "worktree_path": entry.worktree_path,
                        "has_pr": entry.has_pr,
                        "pr_number": entry.pr_number,
                        "blocked_by": list(entry.blocked_by),
                    },
                    indent=2,
                )
        return json.dumps(
            {"error": f"Issue #{issue_number} not in active issues"},
            indent=2,
        )

    @mcp.tool()
    def orchestra_dispatch_history(limit: int = 10) -> str:
        """View recent dispatch execution history.

        Args:
            limit: Maximum number of events to return (default: 10)

        Returns:
            JSON-formatted list of recent dispatch events from flow history
        """
        try:
            from vibe3.clients import SQLiteClient

            safe_limit = max(1, min(limit, 100))
            store = SQLiteClient()
            events = store.get_events(
                branch=None,  # None = query all branches
                event_type="dispatch_result",
                limit=safe_limit,
            )

            formatted_events = [
                {
                    "branch": event.get("branch"),
                    "created_at": event.get("created_at"),
                    "detail": event.get("detail"),
                    "refs": event.get("refs"),
                }
                for event in events
            ]
            return json.dumps(formatted_events, indent=2)
        except Exception as exc:
            logger.bind(domain="orchestra").error(
                f"Failed to get dispatch history: {exc}"
            )
            return json.dumps(
                {"error": f"Failed to get dispatch history: {exc}"},
                indent=2,
            )

    @mcp.tool()
    def orchestra_ask(question: str) -> str:
        """Ask a question about project knowledge and get an answer from a sub-agent.

        Spawns a project explorer agent to answer questions about code structure,
        documentation, conventions, and other static project knowledge.

        Args:
            question: Question about the project
                (e.g., "What is the structure of src/vibe3/?")

        Returns:
            Answer from the project explorer agent, or error message if execution fails
        """
        # Input validation: check for empty or whitespace-only question
        if not question or not question.strip():
            return json.dumps(
                {"error": "Question cannot be empty or whitespace-only"},
                indent=2,
            )

        # Input validation: check question length
        if len(question) > MAX_QUESTION_LENGTH:
            return json.dumps(
                {
                    "error": (
                        f"Question too long. Maximum length is "
                        f"{MAX_QUESTION_LENGTH} characters."
                    )
                },
                indent=2,
            )

        # Input validation: check for forbidden patterns
        question_lower = question.lower()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in question_lower:
                return json.dumps(
                    {"error": f"Question contains forbidden pattern: '{pattern}'"},
                    indent=2,
                )

        try:
            # Resolve repo root for working directory context
            repo_root = resolve_orchestra_repo_root()

            # Read supervisor file
            supervisor_path = repo_root / "supervisor" / "project-explorer.md"
            if not supervisor_path.exists():
                return json.dumps(
                    {"error": "Supervisor file not found"},
                    indent=2,
                )
            supervisor_content = supervisor_path.read_text(encoding="utf-8")

            # Build prompt recipe
            recipe = PromptRecipe(
                template_key="orchestra.explorer",
                variables={
                    "supervisor_content": PromptVariableSource(
                        kind=VariableSourceKind.LITERAL,
                        value=supervisor_content,
                    ),
                    "question": PromptVariableSource(
                        kind=VariableSourceKind.LITERAL,
                        value=question,
                    ),
                },
            )

            # Render prompt
            assembler = PromptAssembler()
            render_result = assembler.render(recipe, runtime_context={})
            prompt = render_result.rendered_text

            # Configure agent options with 180s timeout
            options = AgentOptions(
                agent="vibe-reviewer",
                timeout_seconds=180,
            )

            # Execute via CodeagentBackend
            backend = CodeagentBackend()
            result = backend.run(
                prompt=prompt,
                options=options,
                cwd=repo_root,
                role="explorer",
            )

            # Return sanitized stdout as answer
            sanitized_output = _sanitize_output(result.stdout or "")
            return sanitized_output

        except Exception as exc:
            logger.bind(domain="orchestra").error(
                f"Failed to execute orchestra_ask: {exc}"
            )
            # Sanitize error message to avoid leaking sensitive info
            error_msg = _sanitize_output(str(exc))
            return json.dumps(
                {"error": f"Failed to answer question: {error_msg}"},
                indent=2,
            )

    log = logger.bind(domain="orchestra")
    log.info("MCP server created with 3 resources and 4 tools")
    return mcp
