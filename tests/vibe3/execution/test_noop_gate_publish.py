"""Test for publish path safety net in codeagent_runner."""

from unittest.mock import MagicMock, patch

from vibe3.agents.models import CodeagentCommand
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.models import IssueState


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


class TestPublishPathSafetyNet:
    """Tests for publish path safety net logic."""

    def test_safety_net_fires_before_noop_gate(self) -> None:
        """Safety net should run BEFORE noop gate when conditions are met."""
        agent_result = _make_mock_agent_result()
        mock_store = _make_mock_store()
        # Simulate publish path: commit_mode=True
        mock_store.get_flow_state.return_value = {"commit_mode": "true"}

        command = CodeagentCommand(
            role="executor",
            context_builder=lambda: "publish prompt",
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
                return_value="agent:run",
            ),
            patch(
                "vibe3.execution.codeagent_runner.apply_unified_noop_gate"
            ) as mock_gate,
            patch(
                "vibe3.services.label_service.LabelService"
            ) as mock_label_service_cls,
        ):
            # Before state: merge-ready
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/merge-ready"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()

            # Mock LabelService to simulate state still merge-ready
            mock_label_service = MagicMock()
            mock_label_service.get_state.return_value = IssueState.MERGE_READY
            mock_label_service_cls.return_value = mock_label_service

            service = CodeagentExecutionService()
            result = service.execute_sync(command)

        assert result.success
        # Safety net should have fired
        mock_label_service.get_state.assert_called_once_with(42)
        mock_label_service.set_state.assert_called_once_with(42, IssueState.HANDOFF)
        # Noop gate should still run after safety net
        mock_gate.assert_called_once()

    def test_safety_net_only_for_executor_commit_mode(self) -> None:
        """Safety net should only fire for executor with commit_mode."""
        # Test 1: executor without commit_mode - should not fire
        mock_store_no_commit = _make_mock_store()
        mock_store_no_commit.get_flow_state.return_value = {}

        command_executor = CodeagentCommand(
            role="executor",
            context_builder=lambda: "prompt",
            branch="task/issue-42",
            issue_number=42,
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store_no_commit,
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
                return_value="agent:run",
            ),
            patch("vibe3.execution.codeagent_runner.apply_unified_noop_gate"),
            patch(
                "vibe3.services.label_service.LabelService"
            ) as mock_label_service_cls,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/merge-ready"
            )
            mock_backend.return_value.run.return_value = _make_mock_agent_result()
            mock_opts.return_value = MagicMock()
            mock_label_service = MagicMock()
            mock_label_service_cls.return_value = mock_label_service

            service = CodeagentExecutionService()
            service.execute_sync(command_executor)

        # Safety net should NOT fire (no commit_mode)
        mock_label_service.set_state.assert_not_called()

        # Test 2: planner with commit_mode - should not fire
        mock_store_planner = _make_mock_store()
        mock_store_planner.get_flow_state.return_value = {"commit_mode": "true"}

        command_planner = CodeagentCommand(
            role="planner",
            context_builder=lambda: "prompt",
            branch="task/issue-42",
            issue_number=42,
        )

        with (
            patch(
                "vibe3.execution.codeagent_runner.SQLiteClient",
                return_value=mock_store_planner,
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
            patch("vibe3.execution.codeagent_runner.apply_unified_noop_gate"),
            patch(
                "vibe3.services.label_service.LabelService"
            ) as mock_label_service_cls,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/merge-ready"
            )
            mock_backend.return_value.run.return_value = _make_mock_agent_result()
            mock_opts.return_value = MagicMock()
            mock_label_service = MagicMock()
            mock_label_service_cls.return_value = mock_label_service

            service = CodeagentExecutionService()
            service.execute_sync(command_planner)

        # Safety net should NOT fire (wrong role)
        mock_label_service.set_state.assert_not_called()

    def test_safety_net_skipped_if_state_already_handoff(self) -> None:
        """Safety net should not transition if state is already handoff."""
        agent_result = _make_mock_agent_result()
        mock_store = _make_mock_store()
        mock_store.get_flow_state.return_value = {"commit_mode": "true"}

        command = CodeagentCommand(
            role="executor",
            context_builder=lambda: "publish prompt",
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
                return_value="agent:run",
            ),
            patch("vibe3.execution.codeagent_runner.apply_unified_noop_gate"),
            patch(
                "vibe3.services.label_service.LabelService"
            ) as mock_label_service_cls,
        ):
            # Before state: merge-ready (captured before agent)
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/merge-ready"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()

            # But current state is already handoff (agent succeeded)
            mock_label_service = MagicMock()
            mock_label_service.get_state.return_value = IssueState.HANDOFF
            mock_label_service_cls.return_value = mock_label_service

            service = CodeagentExecutionService()
            service.execute_sync(command)

        # Safety net should check state, but NOT transition
        mock_label_service.get_state.assert_called_once_with(42)
        mock_label_service.set_state.assert_not_called()

    def test_safety_net_uses_label_service_not_subprocess(self) -> None:
        """Verify safety net uses LabelService instead of raw subprocess."""
        agent_result = _make_mock_agent_result()
        mock_store = _make_mock_store()
        mock_store.get_flow_state.return_value = {"commit_mode": "true"}

        command = CodeagentCommand(
            role="executor",
            context_builder=lambda: "publish prompt",
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
                return_value="agent:run",
            ),
            patch("vibe3.execution.codeagent_runner.apply_unified_noop_gate"),
            patch(
                "vibe3.services.label_service.LabelService"
            ) as mock_label_service_cls,
            patch("subprocess.run") as mock_subprocess,  # Should NOT be called
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/merge-ready"
            )
            mock_backend.return_value.run.return_value = agent_result
            mock_opts.return_value = MagicMock()

            mock_label_service = MagicMock()
            mock_label_service.get_state.return_value = IssueState.MERGE_READY
            mock_label_service_cls.return_value = mock_label_service

            service = CodeagentExecutionService()
            service.execute_sync(command)

        # Verify LabelService is used
        mock_label_service.set_state.assert_called_once()
        # Verify subprocess is NOT used for gh issue edit (safety net uses LabelService)
        # Note: subprocess may be called for other purposes (e.g., git operations)
        for call in mock_subprocess.call_args_list:
            args = call[0][0] if call[0] else []
            # Ensure no 'gh issue edit' calls were made
            if args and args[0] == "gh" and "issue" in args and "edit" in args:
                raise AssertionError(
                    f"Safety net should use LabelService, not subprocess. "
                    f"Found gh issue edit call: {args}"
                )
