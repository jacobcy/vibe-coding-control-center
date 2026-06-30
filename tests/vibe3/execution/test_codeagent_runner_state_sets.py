"""State-set capture tests for the synchronous codeagent runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents import CodeagentCommand
from vibe3.execution.codeagent_runner import CodeagentExecutionService


def test_prepare_context_captures_every_remote_state_label() -> None:
    command = CodeagentCommand(
        role="executor",
        context_builder=lambda: "test",
        branch="task/issue-10",
        issue_number=10,
        dry_run=True,
        actor="agent:run",
        resolved_options=MagicMock(),
    )
    service = CodeagentExecutionService()
    service._resolve_command_cwd = MagicMock(return_value=Path.cwd())

    with patch("vibe3.clients.github_client.GitHubClient") as mock_github:
        mock_github.return_value.view_issue.return_value = {
            "labels": [
                {"name": "state/in-progress"},
                {"name": "state/handoff"},
            ],
            "state": "open",
        }
        context = service._prepare_sync_context(command)

    assert context.before_state_label == "state/in-progress"
    assert context.before_state_labels == frozenset(
        {"state/in-progress", "state/handoff"}
    )
