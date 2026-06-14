"""Integration tests for execute_sync gate/callback invocation."""

from unittest.mock import MagicMock, patch

from vibe3.agents import CodeagentCommand
from vibe3.exceptions import AgentExecutionError
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
            patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
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
                    "vibe3.agents.backends.codeagent.CodeagentBackend"
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
            patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
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
            patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
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
            patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
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


class TestTransitionCountFlow:
    """Tests that transition_count flows through executor correctly."""

    def test_transition_count_read_from_flow_state_and_passed_to_gate(self) -> None:
        """Executor reads transition_count from flow_state and passes to gate."""
        mock_store = _make_mock_store()
        mock_store.get_flow_state.return_value = {"transition_count": 5}
        agent_result = _make_mock_agent_result()

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
            patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
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
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        mock_gate.assert_called_once()
        gate_kwargs = mock_gate.call_args[1]
        assert gate_kwargs["flow_state"]["transition_count"] == 5

    def test_transition_count_persisted_after_gate_pass(self) -> None:
        """Executor persists transition_count after gate passes."""
        mock_store = _make_mock_store()
        mock_store.get_flow_state.return_value = {"transition_count": 0}
        agent_result = _make_mock_agent_result()

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
            patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
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
        ):
            # Gate will increment count in flow_state
            mock_gate.side_effect = lambda **kwargs: kwargs["flow_state"].update(
                {"transition_count": 1}
            )
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        mock_gate.assert_called_once()
        # Verify persistence call
        mock_store.update_flow_state.assert_called()
        update_calls = mock_store.update_flow_state.call_args_list
        # Find the call with transition_count
        transition_call = [c for c in update_calls if "transition_count" in c[1]]
        assert len(transition_call) > 0
        assert transition_call[0][1]["transition_count"] == 1


class TestSeverityAwareErrorHandling:
    """Test severity-based error handling in codeagent_runner."""

    def test_agent_execution_metadata_is_recorded_on_failure(self) -> None:
        """Backend diagnostics should reach lifecycle refs.

        Note: error_log recording is now handled by IssueFailed projection hook,
        not directly in codeagent_runner. This test verifies metadata is still
        passed to flow timeline event construction.
        """
        mock_store = _make_mock_store()
        command = CodeagentCommand(
            role="manager",
            context_builder=lambda: "manager prompt",
            branch="task/issue-42",
            issue_number=42,
        )
        exc = AgentExecutionError(
            "codeagent-wrapper failed",
            metadata={
                "backend": "claude",
                "model": "sonnet",
                "prompt_length": "1234",
                "exit_code": "1",
            },
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store,
            ),
            patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
            patch(
                "vibe3.execution.codeagent_runner.load_session_id",
                return_value=None,
            ),
            patch(
                "vibe3.execution.codeagent_runner.resolve_command_agent_options"
            ) as mock_opts,
            patch(
                "vibe3.execution.codeagent_runner.format_agent_actor",
                return_value="agent:manager",
            ),
            patch(
                "vibe3.execution.codeagent_runner.persist_execution_lifecycle_event"
            ) as mock_persist_event,
        ):
            mock_backend.return_value.run.side_effect = exc
            mock_opts.return_value = MagicMock()
            service = CodeagentExecutionService()

            try:
                service.execute_sync(command)
            except AgentExecutionError:
                pass

        # Verify metadata reaches lifecycle event
        refs = mock_persist_event.call_args.kwargs["refs"]
        assert refs["backend"] == "claude"
        assert refs["model"] == "sonnet"
        assert refs["prompt_length"] == "1234"

    def test_warning_does_not_fail_issue(self) -> None:
        """Test that WARNING severity errors don't fail the issue."""
        from vibe3.exceptions.error_classification import get_error_handling_contract
        from vibe3.exceptions.error_severity import ErrorSeverity

        # Get the handling contract for E_EXEC_NO_OUTPUT (WARNING)
        contract = get_error_handling_contract("E_EXEC_NO_OUTPUT")

        # Verify it's WARNING and doesn't fail issue
        assert contract.severity == ErrorSeverity.WARNING
        assert contract.issue_action == "record_only"
        assert contract.gate_action == "ignore"

    def test_critical_fails_issue_immediately(self) -> None:
        """Test that CRITICAL severity triggers immediate FailedGate.

        NOTE: CRITICAL severity does NOT trigger flow block.
        Runtime errors and flow blocks are orthogonal systems:
        - ERROR system: controls FailedGate (dispatch)
        - FLOW BLOCK system: controls business progress (noop_gate, dependencies)
        """
        from vibe3.exceptions.error_classification import get_error_handling_contract
        from vibe3.exceptions.error_severity import ErrorSeverity

        # Get the handling contract for E_MODEL_NOT_FOUND (CRITICAL)
        contract = get_error_handling_contract("E_MODEL_NOT_FOUND")

        # Verify it's CRITICAL and triggers FailedGate immediately
        # But does NOT trigger flow block
        assert contract.severity == ErrorSeverity.CRITICAL
        assert contract.issue_action == "record_only"
        assert contract.gate_action == "immediate"

    def test_error_uses_threshold_gating(self) -> None:
        """Test that ERROR severity uses threshold-based FailedGate.

        NOTE: ERROR severity does NOT trigger flow block.
        Runtime errors and flow blocks are orthogonal systems.
        """
        from vibe3.exceptions.error_classification import get_error_handling_contract
        from vibe3.exceptions.error_severity import ErrorSeverity

        # Get the handling contract for E_API_RATE_LIMIT (ERROR)
        contract = get_error_handling_contract("E_API_RATE_LIMIT")

        # Verify it's ERROR and uses threshold for FailedGate
        # But does NOT trigger flow block
        assert contract.severity == ErrorSeverity.ERROR
        assert contract.issue_action == "record_only"
        assert contract.gate_action == "threshold"
