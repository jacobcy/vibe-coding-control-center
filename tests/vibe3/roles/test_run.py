"""Tests for executor role lifecycle publishing helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.domain.events.flow_lifecycle import IssueFailed
from vibe3.domain.publisher import EventPublisher
from vibe3.roles.run import publish_run_command_failure, publish_run_command_success
from vibe3.roles.run_helpers import ensure_plan_file_exists


class TestPublishRunCommandSuccess:
    """publish_run_command_success records success, does NOT auto-transition state.

    State transitions are the agent's responsibility via run_task instructions.
    Code layer MUST NOT auto-publish HANDOFF (noop-gate-boundary-standard).
    """

    def test_logs_success_without_publishing_events(self) -> None:
        """Success recording should not publish any domain events."""
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=Path("/tmp/handoff.md"),
            session_id="test-session-id",
        )

        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=123,
                _branch="dev/test-123",
                _result=result,
            )

        assert len(published_events) == 0

    def test_logs_success_without_handoff_file(self) -> None:
        """Success without handoff file should also not publish events."""
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=None,
            session_id="test-session-id",
        )

        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=456,
                _branch="dev/test-456",
                _result=result,
            )

        assert len(published_events) == 0

    def test_handles_non_codeagent_result_gracefully(self) -> None:
        """Non-CodeagentResult should also not publish events."""
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=999,
                _branch="dev/test-999",
                _result=object(),
            )

        assert len(published_events) == 0


def test_publish_run_command_failure_emits_issue_failed() -> None:
    EventPublisher.reset()
    published_events = []
    with patch.object(EventPublisher, "publish") as mock_publish:
        mock_publish.side_effect = lambda event: published_events.append(event)
        publish_run_command_failure(
            issue_number=789,
            reason="Execution failed: timeout expired",
        )

    assert len(published_events) == 1
    event = published_events[0]
    assert isinstance(event, IssueFailed)
    assert event.issue_number == 789
    assert "timeout expired" in event.reason
    assert event.actor == "agent:run"


def test_execute_manual_run_no_async_publishes_issue_failed_on_exception() -> None:
    """When execute_sync raises in no_async mode, publish_run_command_failure is called.

    Verifies that exceptions in the non-skill no_async path trigger failure
    publishing before re-raising.
    """
    from unittest.mock import MagicMock, patch

    from vibe3.roles.run_command import execute_manual_run

    with (
        patch("vibe3.roles.run_command.CodeagentExecutionService") as mock_svc_cls,
        patch("vibe3.roles.run_command.SQLiteClient") as mock_sqlite_cls,
        patch(
            "vibe3.roles.run_command.publish_run_command_failure"
        ) as mock_publish_failure,
    ):
        mock_sqlite_cls.return_value.get_flow_state.return_value = None
        mock_svc_cls.return_value.execute_sync.side_effect = RuntimeError(
            "backend returned empty result"
        )

        with pytest.raises(RuntimeError, match="backend returned empty result"):
            execute_manual_run(
                config=MagicMock(),
                branch="task/issue-349",
                issue_number=349,
                instructions=None,
                plan_file=None,
                skill=None,
                summary=MagicMock(mode="plan"),
                dry_run=False,
                no_async=True,
                show_prompt=False,
                agent=None,
                backend=None,
                model=None,
            )

    mock_publish_failure.assert_called_once_with(
        issue_number=349,
        reason="backend returned empty result",
    )


class TestExecutorNoOpGate:
    """Executor no-op gate: state 未变 → blocked"""

    def test_executor_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Executor state/in-progress 未变 → blocked"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue.failure.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/in-progress"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=200,
                branch="task/issue-200",
                actor="agent:run",
                role="executor",
                before_state_label="state/in-progress",
            )

        mock_block.assert_called_once()

    def test_executor_pass_when_state_changed(
        self,
    ) -> None:
        """Executor state/in-progress → state/handoff → pass"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue.failure.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/handoff"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=200,
                branch="task/issue-200",
                actor="agent:run",
                role="executor",
                before_state_label="state/in-progress",
            )

        mock_block.assert_not_called()


class TestEnsurePlanFileExists:
    """Tests for ensure_plan_file_exists utility."""

    def test_ensure_plan_file_exists_with_absolute_path(self, tmp_path):
        """Absolute path that exists should pass."""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Plan\n")

        # Should not raise
        ensure_plan_file_exists(str(plan_file))

    def test_ensure_plan_file_exists_with_missing_absolute_path(self):
        """Absolute path that doesn't exist should raise."""
        with pytest.raises(FileNotFoundError):
            ensure_plan_file_exists("/nonexistent/path/plan.md")

    def test_ensure_plan_file_exists_with_none(self):
        """None plan_file should be a no-op."""
        # Should not raise
        ensure_plan_file_exists(None)

    def test_ensure_plan_file_exists_uses_resolve_handoff_target(
        self, tmp_path, monkeypatch
    ):
        """Verify it uses resolve_handoff_target for relative paths."""

        # Create a worktree with plan file
        worktree_root = tmp_path / "worktree"
        worktree_root.mkdir()
        plan_dir = worktree_root / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test-plan.md"
        plan_file.write_text("# Plan\n")

        calls = []

        def mock_resolve(target, branch=None, git_client=None):
            calls.append((target, branch))
            if (
                str(target) == "docs/plans/test-plan.md"
                and branch == "task/test-branch"
            ):
                return plan_file
            raise FileNotFoundError(f"Mock: {target}")

        # Mock the public API import (cross-module call uses public API)
        monkeypatch.setattr(
            "vibe3.services.resolve_handoff_target",
            mock_resolve,
        )

        # Should call resolve_handoff_target with branch
        ensure_plan_file_exists("docs/plans/test-plan.md", branch="task/test-branch")

        # Verify it was called with correct args
        assert len(calls) == 1
        assert calls[0] == ("docs/plans/test-plan.md", "task/test-branch")
