"""Tests for supervisor_run_service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.orchestra import supervisor_run_service
from vibe3.orchestra.config import OrchestraConfig

runner = CliRunner(env={"NO_COLOR": "1"})


def test_run_supervisor_mode_dry_run_prints_plan() -> None:
    """Test that dry run mode prints the plan without executing."""
    mock_config = OrchestraConfig(
        repo="owner/repo",
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )

    with (
        patch.object(
            supervisor_run_service.OrchestraConfig,
            "from_settings",
            return_value=mock_config,
        ),
        patch.object(
            supervisor_run_service.GovernanceService,
            "__init__",
            return_value=None,
        ),
        patch.object(
            supervisor_run_service.GovernanceService,
            "render_current_plan",
            return_value="# Supervisor Plan\n\n## Task 1\n- Do something",
        ),
    ):
        # Should not raise or exit
        supervisor_run_service.run_supervisor_mode(
            supervisor_file="supervisor/test.md",
            issue_number=None,
            dry_run=True,
            async_mode=False,
        )


def test_run_supervisor_mode_async_starts_session() -> None:
    """Test that async mode starts tmux session."""
    mock_config = OrchestraConfig(
        repo="owner/repo",
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )
    mock_backend = MagicMock()
    mock_backend.start_async.return_value = AsyncExecutionHandle(
        tmux_session="vibe3-supervisor-test",
        log_path=Path("temp/logs/vibe3-supervisor-test.async.log"),
        prompt_file_path=Path("/tmp/prompt.md"),
    )

    with (
        patch.object(
            supervisor_run_service.OrchestraConfig,
            "from_settings",
            return_value=mock_config,
        ),
        patch.object(
            supervisor_run_service.GovernanceService,
            "__init__",
            return_value=None,
        ),
        patch.object(
            supervisor_run_service.GovernanceService,
            "render_current_plan",
            return_value="# Plan",
        ),
        patch.object(
            supervisor_run_service.VibeConfig,
            "get_defaults",
            return_value=MagicMock(run=MagicMock(run_prompt="Test prompt")),
        ),
        patch.object(
            supervisor_run_service.CodeagentExecutionService,
            "resolve_agent_options",
            return_value=MagicMock(),
        ),
        patch.object(
            supervisor_run_service,
            "CodeagentBackend",
            return_value=mock_backend,
        ),
    ):
        supervisor_run_service.run_supervisor_mode(
            supervisor_file="supervisor/test.md",
            issue_number=None,
            dry_run=False,
            async_mode=True,
        )

        mock_backend.start_async.assert_called_once()
        call_kwargs = mock_backend.start_async.call_args.kwargs
        assert call_kwargs["execution_name"] == "vibe3-supervisor-test"


def test_run_supervisor_mode_sync_runs_backend() -> None:
    """Test that sync mode runs backend synchronously."""
    mock_config = OrchestraConfig(
        repo="owner/repo",
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )
    mock_backend = MagicMock()
    mock_backend.run.return_value = MagicMock(is_success=lambda: True)

    with (
        patch.object(
            supervisor_run_service.OrchestraConfig,
            "from_settings",
            return_value=mock_config,
        ),
        patch.object(
            supervisor_run_service.GovernanceService,
            "__init__",
            return_value=None,
        ),
        patch.object(
            supervisor_run_service.GovernanceService,
            "render_current_plan",
            return_value="# Plan",
        ),
        patch.object(
            supervisor_run_service.VibeConfig,
            "get_defaults",
            return_value=MagicMock(run=MagicMock(run_prompt="Test prompt")),
        ),
        patch.object(
            supervisor_run_service.CodeagentExecutionService,
            "resolve_agent_options",
            return_value=MagicMock(),
        ),
        patch.object(
            supervisor_run_service,
            "CodeagentBackend",
            return_value=mock_backend,
        ),
    ):
        supervisor_run_service.run_supervisor_mode(
            supervisor_file="supervisor/test.md",
            issue_number=None,
            dry_run=False,
            async_mode=False,
        )

        mock_backend.run.assert_called_once()


def test_build_supervisor_task_returns_none_for_no_issue() -> None:
    """Test that build_supervisor_task returns None when no issue number."""
    config = OrchestraConfig(
        repo="owner/repo",
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )

    result = supervisor_run_service.build_supervisor_task(
        config=config,
        issue_number=None,
    )

    assert result is None


def test_build_supervisor_task_builds_issue_task() -> None:
    """Test that build_supervisor_task builds correct task for issue."""
    config = OrchestraConfig(
        repo="owner/repo",
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )
    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "number": 123,
        "title": "Test Issue Title",
    }

    with patch.object(supervisor_run_service, "GitHubClient", return_value=mock_github):
        result = supervisor_run_service.build_supervisor_task(
            config=config,
            issue_number=123,
        )

        assert result is not None
        assert "Process governance issue #123" in result
        assert "Test Issue Title" in result
        assert "in repo owner/repo" in result


def test_resolve_issue_supervisor_file_returns_configured_file() -> None:
    """Test that resolve_issue_supervisor_file returns from config."""
    mock_config = OrchestraConfig(
        repo="owner/repo",
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )
    mock_config.supervisor_handoff.supervisor_file = "supervisor/apply.md"

    with patch.object(
        supervisor_run_service.OrchestraConfig,
        "from_settings",
        return_value=mock_config,
    ):
        result = supervisor_run_service.resolve_issue_supervisor_file()

        assert result == "supervisor/apply.md"
