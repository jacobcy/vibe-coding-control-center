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

    def test_gate_skipped_without_issue_number_or_branch(self) -> None:
        """Gate does not fire when issue_number or branch is None."""
        # Test 1: No issue_number
        command_no_issue = CodeagentCommand(
            role="planner",
            context_builder=lambda: "test prompt",
            branch="task/issue-42",
            issue_number=None,
        )
        # Test 2: No branch
        command_no_branch = CodeagentCommand(
            role="planner",
            context_builder=lambda: "test prompt",
            branch=None,
            issue_number=42,
        )

        for command in [command_no_issue, command_no_branch]:
            with (
                patch(
                    "vibe3.execution.codeagent_runner.CodeagentBackend"
                ) as mock_backend,
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
                    "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
                ) as mock_gate,
            ):
                mock_backend.return_value.run.return_value = _make_mock_agent_result()
                mock_opts.return_value = MagicMock()
                service = CodeagentExecutionService()
                result = service.execute_sync(command)

            assert result.success
            mock_gate.assert_not_called()

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

    def test_executor_records_passive_run_artifact_when_report_ref_missing(
        self,
    ) -> None:
        """Executor should auto-record shared run artifact for manager visibility."""
        agent_result = _make_mock_agent_result(
            stdout="### Modified Files\n- src/demo.py\n"
        )
        mock_store = _make_mock_store()
        mock_store.get_flow_state.return_value = {}

        command = CodeagentCommand(
            role="executor",
            context_builder=lambda: "run prompt",
            branch="task/issue-42",
            issue_number=42,
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
                return_value="agent:run",
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
            ) as mock_gate,
            patch(
                "vibe3.execution.codeagent_runner.HandoffService"
            ) as mock_handoff_cls,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/in-progress"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            mock_handoff = MagicMock()
            mock_handoff.record_passive_artifact.return_value = "shared/run.md"
            mock_handoff_cls.return_value = mock_handoff

            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        mock_gate.assert_called_once()
        mock_handoff.record_passive_artifact.assert_called_once()
        assert result.handoff_file == "shared/run.md"

    def test_executor_records_passive_run_when_no_active_handoff_even_if_ref_exists(
        self,
    ) -> None:
        """Executor should record passive artifact when no active handoff this round.

        New logic: Passive recording triggers when handoff_file is None
        (no active handoff), regardless of whether authoritative ref exists.
        This ensures every execution round is recorded, even if authoritative
        ref was set by previous rounds.
        """
        agent_result = _make_mock_agent_result(stdout="run output")
        mock_store = _make_mock_store()
        mock_store.get_flow_state.return_value = {"report_ref": "docs/reports/run.md"}

        command = CodeagentCommand(
            role="executor",
            context_builder=lambda: "run prompt",
            branch="task/issue-42",
            issue_number=42,
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
                return_value="agent:run",
            ),
            patch("vibe3.execution.codeagent_runner.apply_unified_noop_gate"),
            patch(
                "vibe3.execution.codeagent_runner.HandoffService"
            ) as mock_handoff_cls,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/in-progress"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()

            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        # New logic: passive recording happens because no active handoff occurred
        mock_handoff_cls.return_value.record_passive_artifact.assert_called_once()
