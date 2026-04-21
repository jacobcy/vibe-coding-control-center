"""Integration tests for execute_sync gate/callback invocation."""

from unittest.mock import MagicMock, patch

from vibe3.agents.models import CodeagentCommand
from vibe3.execution.codeagent_runner import (
    CodeagentExecutionService,
)


def _make_mock_store() -> MagicMock:
    """Create a mock SQLiteClient."""
    store = MagicMock()
    store.get_flow_state.return_value = {}
    return store


def _make_github_issue_payload(state_label: str = "state/plan") -> dict:
    """Build a GitHub issue payload dict with given state label."""
    labels = [{"name": state_label}] if state_label else []
    return {"labels": labels, "state": "open"}


def _make_mock_agent_result(success: bool = True, stdout: str = "done") -> MagicMock:
    result = MagicMock()
    result.is_success.return_value = success
    result.exit_code = 0 if success else 1
    result.stdout = stdout
    result.stderr = ""
    result.session_id = "test-session"
    return result


class TestExecuteSyncGateIntegration:
    """Tests that execute_sync invokes the gate correctly."""

    def test_gate_fires_with_issue_number(self) -> None:
        """Gate fires when issue_number is provided."""
        agent_result = _make_mock_agent_result()
        mock_store = _make_mock_store()

        command = CodeagentCommand(
            role="planner",
            context_builder=lambda: "test prompt",
            branch="task/issue-42",
            issue_number=42,
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store,
            ),
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("vibe3.execution.codeagent_runner.CodeagentBackend") as mock_backend,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:plan",
            ),
            patch(
                "vibe3.execution.codeagent_runner.record_handoff_unified",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
            ) as mock_gate,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/plan"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        mock_gate.assert_called_once()
        call_kwargs = mock_gate.call_args[1]
        assert call_kwargs["issue_number"] == 42
        assert call_kwargs["role"] == "planner"

    def test_gate_skipped_without_issue_number(self) -> None:
        """Gate does not fire when issue_number is None."""
        agent_result = _make_mock_agent_result()
        mock_store = _make_mock_store()

        command = CodeagentCommand(
            role="planner",
            context_builder=lambda: "test prompt",
            branch="task/issue-42",
            issue_number=None,
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store,
            ),
            patch("vibe3.execution.codeagent_runner.CodeagentBackend") as mock_backend,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:plan",
            ),
            patch(
                "vibe3.execution.codeagent_runner.record_handoff_unified",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
            ) as mock_gate,
        ):
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        mock_gate.assert_not_called()

    def test_gate_skipped_without_branch(self) -> None:
        """Gate does not fire when branch is None."""
        command = CodeagentCommand(
            role="planner",
            context_builder=lambda: "test prompt",
            branch=None,
            issue_number=42,
        )

        with (
            patch("vibe3.execution.codeagent_runner.CodeagentBackend") as mock_backend,
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:plan",
            ),
            patch(
                "vibe3.execution.codeagent_runner.record_handoff_unified",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
            ) as mock_gate,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/plan"
            )
            mock_backend.return_value.run.return_value = _make_mock_agent_result()
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        mock_gate.assert_not_called()

    def test_pre_gate_callback_fires_before_gate(self) -> None:
        """pre_gate_callback is called before the sync gate."""
        agent_result = _make_mock_agent_result(stdout="verdict: APPROVE")
        mock_store = _make_mock_store()
        callback = MagicMock()

        command = CodeagentCommand(
            role="reviewer",
            context_builder=lambda: "review prompt",
            branch="task/issue-77",
            issue_number=77,
            pre_gate_callback=callback,
        )

        call_order = []
        callback.side_effect = lambda **kw: call_order.append("callback")

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store,
            ),
            patch("vibe3.execution.codeagent_runner.CodeagentBackend") as mock_backend,
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:review",
            ),
            patch(
                "vibe3.execution.codeagent_runner.record_handoff_unified",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate",
                side_effect=lambda **kw: call_order.append("gate"),
            ),
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            service.execute_sync(command)

        assert call_order == ["callback", "gate"]
        callback.assert_called_once_with(
            issue_number=77,
            branch="task/issue-77",
            actor="agent:review",
            stdout="verdict: APPROVE",
        )

    def test_before_state_label_captured_before_agent(self) -> None:
        """before_state_label is captured from GitHub before agent execution."""
        mock_store = _make_mock_store()
        agent_result = _make_mock_agent_result()
        agent_result.is_success.return_value = True

        command = CodeagentCommand(
            role="planner",
            context_builder=lambda: "test",
            branch="task/issue-10",
            issue_number=10,
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store,
            ),
            patch("vibe3.execution.codeagent_runner.CodeagentBackend") as mock_backend,
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:plan",
            ),
            patch(
                "vibe3.execution.codeagent_runner.record_handoff_unified",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
            ) as mock_gate,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/plan"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            service.execute_sync(command)

        # Verify before_state_label was captured from GitHub
        gate_kwargs = mock_gate.call_args[1]
        assert gate_kwargs["before_state_label"] == "state/plan"

    def test_async_child_marker_does_not_change_sync_shell_behavior(
        self, monkeypatch
    ) -> None:
        """Async-child marker must not alter sync shell behavior."""
        monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
        agent_result = _make_mock_agent_result(stdout="review output")
        mock_store = _make_mock_store()
        callback = MagicMock()

        command = CodeagentCommand(
            role="reviewer",
            context_builder=lambda: "review prompt",
            branch="task/issue-88",
            issue_number=88,
            pre_gate_callback=callback,
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store,
            ),
            patch("vibe3.execution.codeagent_runner.CodeagentBackend") as mock_backend,
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:review",
            ),
            patch(
                "vibe3.execution.codeagent_runner.record_handoff_unified",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
            ) as mock_gate,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            service.execute_sync(command)

        callback.assert_called_once_with(
            issue_number=88,
            branch="task/issue-88",
            actor="agent:review",
            stdout="review output",
        )
        mock_gate.assert_called_once()

    def test_execute_sync_runs_handoff_callback_and_noop_gate_in_order(
        self,
    ) -> None:
        """execute_sync must run handoff -> callback -> gate in that order."""
        from pathlib import Path

        agent_result = _make_mock_agent_result(stdout="verdict: APPROVE")
        mock_store = _make_mock_store()

        events: list[str] = []

        def fake_record(*args, **kwargs) -> Path | None:
            events.append("handoff")
            return Path("/tmp/handoff.md")

        def fake_callback(**kwargs) -> None:
            events.append("callback")

        def fake_gate(**kwargs) -> None:
            events.append("gate")

        command = CodeagentCommand(
            role="reviewer",
            context_builder=lambda: "review prompt",
            branch="task/issue-99",
            issue_number=99,
            pre_gate_callback=fake_callback,
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store,
            ),
            patch("vibe3.execution.codeagent_runner.CodeagentBackend") as mock_backend,
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:review",
            ),
            patch(
                "vibe3.execution.codeagent_runner.record_handoff_unified",
                side_effect=fake_record,
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate",
                side_effect=fake_gate,
            ),
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        assert events == ["handoff", "callback", "gate"]
