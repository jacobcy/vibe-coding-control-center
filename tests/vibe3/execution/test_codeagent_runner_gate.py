"""Tests for the unified no-op gate in codeagent_runner."""

from unittest.mock import MagicMock, patch

from vibe3.agents.models import CodeagentCommand
from vibe3.execution.codeagent_runner import (
    CodeagentExecutionService,
    _apply_unified_noop_gate,
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


class TestApplyUnifiedNoopGate:
    """Tests for the simplified no-op gate."""

    def test_missing_ref_still_blocks_when_state_unchanged(self) -> None:
        """Missing ref does not matter when state is unchanged: still block."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/plan"
            )
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert call_kwargs["issue_number"] == 42
        assert "state unchanged" in call_kwargs["reason"]
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_unchanged"

    def test_ref_present_state_unchanged_blocks(self) -> None:
        """Ref presence does not matter when state is unchanged: block."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/plan"
            )
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert "state unchanged" in call_kwargs["reason"]
        store.add_event.assert_called_once()

    def test_state_changed_passes(self) -> None:
        """State change is the only pass condition."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/ready"
            )
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"
        assert "state/plan" in event_args[1]["detail"]
        assert "state/ready" in event_args[1]["detail"]

    def test_blocks_executor_when_state_unchanged(self) -> None:
        """Executor is blocked when state is unchanged."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/run"
            )
            _apply_unified_noop_gate(
                store=store,
                issue_number=99,
                branch="task/issue-99",
                actor="agent:run",
                role="executor",
                before_state_label="state/run",
            )

        mock_block.assert_called_once()

    def test_blocks_manager_when_state_unchanged_and_passes_repo(self) -> None:
        """Manager block helper must receive repo to avoid post-gate crash."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_manager_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/ready"
            )
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:manager",
                role="manager",
                before_state_label="state/ready",
                repo="owner/repo",
            )

        mock_block.assert_called_once()
        assert mock_block.call_args.kwargs["repo"] == "owner/repo"

    def test_blocks_reviewer_when_state_unchanged(self) -> None:
        """Reviewer is blocked when state is unchanged."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            _apply_unified_noop_gate(
                store=store,
                issue_number=55,
                branch="task/issue-55",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
            )

        mock_block.assert_called_once()

    def test_blocks_when_github_returns_none(self) -> None:
        """Gate blocks when GitHub returns None (fail-safe)."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = None
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        assert "cannot verify remote state" in mock_block.call_args.kwargs["reason"]
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "cannot_verify_remote_state"

    def test_blocks_when_github_raises(self) -> None:
        """Gate blocks when GitHub call raises (fail-safe)."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.side_effect = Exception("timeout")
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        assert "cannot verify remote state" in mock_block.call_args.kwargs["reason"]
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "cannot_verify_remote_state"

    def test_blocks_when_state_label_disappears(self) -> None:
        """Gate blocks when state label disappears from issue after agent."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                ""
            )  # No state label
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        assert "disappeared" in mock_block.call_args.kwargs["reason"]
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "state_unchanged"

    def test_gate_skipped_when_no_state_label(self) -> None:
        """Gate skips when issue has no state/ label.

        Issues not managed by state machine (e.g. manual ``vibe3 run``)
        should bypass the no-op gate entirely.
        """
        store = _make_mock_store()

        with patch(
            "vibe3.services.issue_failure_service.block_executor_noop_issue"
        ) as mock_block:
            _apply_unified_noop_gate(
                store=store,
                issue_number=99,
                branch="task/issue-99",
                actor="agent:run",
                role="executor",
                before_state_label="",  # No state label
            )

        # Gate should skip, not block
        mock_block.assert_not_called()
        store.add_event.assert_not_called()

    def test_gate_skipped_when_before_state_label_none(self) -> None:
        """Gate is skipped when before_state_label is None."""
        store = _make_mock_store()

        with patch(
            "vibe3.services.issue_failure_service.block_planner_noop_issue"
        ) as mock_block:
            _apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label=None,  # None state label
            )

        # Gate should skip, not block
        mock_block.assert_not_called()
        store.add_event.assert_not_called()


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
                "vibe3.execution.codeagent_runner._apply_unified_noop_gate"
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
                "vibe3.execution.codeagent_runner._apply_unified_noop_gate"
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
                "vibe3.execution.codeagent_runner._apply_unified_noop_gate"
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
                "vibe3.execution.codeagent_runner._apply_unified_noop_gate",
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
                "vibe3.execution.codeagent_runner._apply_unified_noop_gate"
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
                "vibe3.execution.codeagent_runner._apply_unified_noop_gate"
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
