"""Tests for governance_sync_runner error tracking integration.

These tests verify that API errors in the governance sync execution path
are properly captured by ErrorTrackingService for FailedGate threshold checking.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestGovernanceSyncRunner:
    """Test governance sync runner error tracking."""

    @patch("vibe3.execution.governance_sync_runner.append_governance_event")
    @patch(
        "vibe3.execution.governance_sync_runner.render_governance_prompt",
        return_value=MagicMock(rendered_text="Test prompt"),
    )
    @patch(
        "vibe3.execution.governance_sync_runner.resolve_governance_options",
        return_value=MagicMock(backend="claude", model="sonnet"),
    )
    @patch(
        "vibe3.execution.governance_sync_runner.build_governance_snapshot_context",
        return_value={},
    )
    @patch("vibe3.execution.governance_sync_runner.CodeagentBackend")
    @patch("vibe3.execution.governance_sync_runner.OrchestraStatusService")
    @patch("vibe3.execution.governance_sync_runner.FlowManager")
    @patch("vibe3.execution.governance_sync_runner.load_orchestra_config")
    def test_dry_run_shows_intent(
        self,
        mock_load_config: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
        mock_backend_cls: MagicMock,
        mock_snapshot_ctx: MagicMock,
        mock_resolve_opts: MagicMock,
        mock_render: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        """Dry run should print intent without executing."""
        from vibe3.execution.governance_sync_runner import run_governance_sync

        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_load_config.return_value = mock_config

        mock_status = MagicMock()
        snapshot = MagicMock()
        snapshot.circuit_breaker_state = "closed"
        mock_status.snapshot.return_value = snapshot
        mock_status_cls.return_value = mock_status

        run_governance_sync(
            tick_count=5,
            dry_run=True,
            show_prompt=False,
            session_id=None,
        )

        # Dry run should not dispatch to backend
        mock_append_event.assert_not_called()

    @patch("vibe3.execution.governance_sync_runner.append_governance_event")
    @patch(
        "vibe3.execution.governance_sync_runner.render_governance_prompt",
        return_value=MagicMock(rendered_text="Test prompt"),
    )
    @patch(
        "vibe3.execution.governance_sync_runner.resolve_governance_options",
        return_value=MagicMock(backend="claude", model="sonnet"),
    )
    @patch(
        "vibe3.execution.governance_sync_runner.build_governance_snapshot_context",
        return_value={},
    )
    @patch("vibe3.execution.governance_sync_runner.CodeagentBackend")
    @patch("vibe3.execution.governance_sync_runner.OrchestraStatusService")
    @patch("vibe3.execution.governance_sync_runner.FlowManager")
    @patch("vibe3.execution.governance_sync_runner.load_orchestra_config")
    def test_success_path_logs_completion(
        self,
        mock_load_config: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
        mock_backend_cls: MagicMock,
        mock_snapshot_ctx: MagicMock,
        mock_resolve_opts: MagicMock,
        mock_render: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        """Successful execution should log completion event."""
        from vibe3.execution.governance_sync_runner import run_governance_sync

        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_load_config.return_value = mock_config

        mock_status = MagicMock()
        snapshot = MagicMock()
        snapshot.circuit_breaker_state = "closed"
        mock_status.snapshot.return_value = snapshot
        mock_status_cls.return_value = mock_status

        mock_backend = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.is_success.return_value = True
        mock_backend.run.return_value = mock_result
        mock_backend_cls.return_value = mock_backend

        run_governance_sync(
            tick_count=5,
            dry_run=False,
            show_prompt=False,
            session_id=None,
        )

        # Should log completion event
        mock_append_event.assert_called()
        call_args = mock_append_event.call_args.args[0]
        assert "completed" in call_args or "tick=5" in call_args

    @patch("vibe3.execution.governance_sync_runner.append_governance_event")
    @patch(
        "vibe3.execution.governance_sync_runner.render_governance_prompt",
        return_value=MagicMock(rendered_text="Test prompt"),
    )
    @patch(
        "vibe3.execution.governance_sync_runner.resolve_governance_options",
        return_value=MagicMock(backend="claude", model="sonnet"),
    )
    @patch(
        "vibe3.execution.governance_sync_runner.build_governance_snapshot_context",
        return_value={},
    )
    @patch("vibe3.execution.governance_sync_runner.CodeagentBackend")
    @patch("vibe3.execution.governance_sync_runner.OrchestraStatusService")
    @patch("vibe3.execution.governance_sync_runner.FlowManager")
    @patch("vibe3.execution.governance_sync_runner.load_orchestra_config")
    def test_error_path_records_to_error_tracking(
        self,
        mock_load_config: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
        mock_backend_cls: MagicMock,
        mock_snapshot_ctx: MagicMock,
        mock_resolve_opts: MagicMock,
        mock_render: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        """API error should be classified and recorded to ErrorTrackingService."""
        from vibe3.execution.governance_sync_runner import run_governance_sync

        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_load_config.return_value = mock_config

        mock_status = MagicMock()
        snapshot = MagicMock()
        snapshot.circuit_breaker_state = "closed"
        mock_status.snapshot.return_value = snapshot
        mock_status_cls.return_value = mock_status

        mock_backend = MagicMock()
        # Simulate API error
        mock_backend.run.side_effect = RuntimeError("API error: rate limited")
        mock_backend_cls.return_value = mock_backend

        # Patch at the source module where ErrorTrackingService is imported
        with patch(
            "vibe3.services.error_tracking_service.ErrorTrackingService"
        ) as mock_tracking_cls:
            mock_tracking = MagicMock()
            mock_tracking_cls.get_instance.return_value = mock_tracking

            with pytest.raises(RuntimeError):
                run_governance_sync(
                    tick_count=5,
                    dry_run=False,
                    show_prompt=False,
                    session_id=None,
                )

            # Should classify and record error
            mock_tracking.record_error.assert_called_once()
            call_args = mock_tracking.record_error.call_args
            # Check keyword arguments
            assert call_args.kwargs["error_code"] == "E_API_RATE_LIMIT"
            assert call_args.kwargs["tick_id"] == 5
            assert call_args.kwargs["issue_number"] is None
            assert call_args.kwargs["branch"] is None

        # Should also log governance event
        mock_append_event.assert_called()


class TestGovernanceAsyncRunnerSkipPaths:
    """Test governance async skip paths: concurrent limit and circuit breaker."""

    @patch("vibe3.execution.governance_sync_runner.append_governance_event")
    @patch("vibe3.execution.governance_sync_runner.echo")
    @patch("vibe3.execution.governance_sync_runner.get_store")
    def test_skip_when_concurrent_governance_at_limit(
        self,
        mock_get_store: MagicMock,
        mock_echo: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        """Async dispatch should be skipped when concurrent sessions >= limit."""
        mock_config = MagicMock()
        mock_config.governance_max_concurrent = 1

        mock_registry = MagicMock()
        mock_registry.list_live_governance_sessions.return_value = [
            {"tmux_session": "vibe3-governance-tick-0"},
        ]
        mock_registry.mark_governance_sessions_done_when_tmux_gone = MagicMock()
        mock_store_ctx = MagicMock()
        mock_store_ctx.__enter__ = MagicMock(return_value=mock_store_ctx)
        mock_store_ctx.__exit__ = MagicMock(return_value=False)
        mock_get_store.return_value = mock_store_ctx

        with (
            patch(
                "vibe3.execution.governance_sync_runner.load_orchestra_config",
                return_value=mock_config,
            ),
            patch(
                "vibe3.execution.governance_sync_runner.CodeagentBackend",
                return_value=MagicMock(),
            ),
            patch(
                "vibe3.environment.session_registry.SessionRegistryService",
                return_value=mock_registry,
            ),
        ):
            from vibe3.execution.governance_sync_runner import run_governance_async

            run_governance_async(tick_count=0)

        mock_echo.assert_called_once()
        assert "governance already running" in mock_echo.call_args[0][0]
        mock_append_event.assert_called_once()
        assert "dispatch skipped" in mock_append_event.call_args[0][0]

    @patch("vibe3.execution.governance_sync_runner.append_governance_event")
    @patch("vibe3.execution.governance_sync_runner.echo")
    @patch("vibe3.execution.governance_sync_runner.get_store")
    def test_skip_when_circuit_breaker_open(
        self,
        mock_get_store: MagicMock,
        mock_echo: MagicMock,
        mock_append_event: MagicMock,
    ) -> None:
        """Async dispatch should be skipped when circuit breaker is open."""
        mock_config = MagicMock()
        mock_config.governance_max_concurrent = 3

        mock_registry = MagicMock()
        mock_registry.list_live_governance_sessions.return_value = []
        mock_registry.mark_governance_sessions_done_when_tmux_gone = MagicMock()
        mock_store_ctx = MagicMock()
        mock_store_ctx.__enter__ = MagicMock(return_value=mock_store_ctx)
        mock_store_ctx.__exit__ = MagicMock(return_value=False)
        mock_get_store.return_value = mock_store_ctx

        mock_snapshot = MagicMock()
        mock_snapshot.circuit_breaker_state = "open"
        mock_status_service = MagicMock()
        mock_status_service.snapshot.return_value = mock_snapshot

        with (
            patch(
                "vibe3.execution.governance_sync_runner.load_orchestra_config",
                return_value=mock_config,
            ),
            patch(
                "vibe3.execution.governance_sync_runner.CodeagentBackend",
                return_value=MagicMock(),
            ),
            patch(
                "vibe3.environment.session_registry.SessionRegistryService",
                return_value=mock_registry,
            ),
            patch(
                "vibe3.orchestra.flow_dispatch.FlowManager",
            ),
            patch(
                "vibe3.execution.governance_sync_runner.OrchestraStatusService",
                return_value=mock_status_service,
            ),
            patch(
                "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
                return_value=MagicMock(),
            ),
            patch(
                "vibe3.execution.coordinator.ExecutionCoordinator",
            ),
        ):
            from vibe3.execution.governance_sync_runner import run_governance_async

            run_governance_async(tick_count=5)

        mock_echo.assert_called_once()
        assert "circuit breaker is OPEN" in mock_echo.call_args[0][0]
        mock_append_event.assert_called_once()
        assert "circuit breaker OPEN" in mock_append_event.call_args[0][0]
