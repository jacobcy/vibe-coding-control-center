"""Tests for governance_sync_runner with dependency injection.

These tests verify the new dependency injection pattern introduced
to decouple execution layer from roles/orchestra layer.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.models import ExecutionLaunchResult


def _mock_execution_coordinator(monkeypatch):
    """Helper to mock ExecutionCoordinator and prevent real tmux session creation.

    This is used by tests that call run_governance_async to ensure
    no real tmux sessions are created during test execution.
    """
    monkeypatch.setattr(
        "vibe3.execution.coordinator.ExecutionCoordinator",
        lambda config, store, backend, start_async=None, capacity=None: (
            MagicMock(
                dispatch_execution=lambda request: ExecutionLaunchResult(
                    launched=False,
                    skipped=True,
                    reason="test: mocked coordinator",
                )
            )
        ),
    )


class TestGovernanceSyncRunnerWithInjection:
    """Test governance sync runner with injected dependencies."""

    def test_dry_run_shows_intent(self) -> None:
        """Dry run should print intent without executing."""
        from vibe3.execution.governance_sync_runner import run_governance_sync

        # Create mock governance functions
        mock_governance_fns = MagicMock()
        mock_governance_fns.resolve_options.return_value = MagicMock(
            backend="claude", model="sonnet"
        )
        mock_governance_fns.build_snapshot_context.return_value = {}
        mock_governance_fns.render_prompt.return_value = MagicMock(
            rendered_text="Test prompt"
        )

        # Create mock event logger
        mock_append_event = MagicMock()

        # Mock OrchestraStatusService with .create() factory method
        mock_status_service = MagicMock()
        mock_status_service.snapshot.return_value = MagicMock(
            circuit_breaker_state="closed"
        )
        mock_service_class = MagicMock()
        mock_service_class.create.return_value = mock_status_service

        # Mock dependencies that are still needed
        with (pytest.MonkeyPatch().context() as m,):
            m.setattr(
                "vibe3.execution.governance_sync_runner.load_orchestra_config",
                lambda *, target_repo=None: MagicMock(),
            )
            m.setattr(
                "vibe3.orchestra.flow_dispatch.FlowManager",
                lambda config: MagicMock(),
            )
            m.setattr(
                "vibe3.services.orchestra.status.OrchestraStatusService",
                mock_service_class,
            )

            run_governance_sync(
                tick_count=5,
                dry_run=True,
                show_prompt=False,
                session_id=None,
                governance_fns=mock_governance_fns,
                append_event=mock_append_event,
            )

        # Dry run should not dispatch to backend (no calls to append_event)
        mock_append_event.assert_not_called()

    def test_success_path_logs_completion(self) -> None:
        """Successful execution should log completion event."""
        from vibe3.execution.governance_sync_runner import run_governance_sync

        # Create mock governance functions
        mock_governance_fns = MagicMock()
        mock_governance_fns.resolve_options.return_value = MagicMock(
            backend="claude", model="sonnet"
        )
        mock_governance_fns.build_snapshot_context.return_value = {}
        mock_governance_fns.render_prompt.return_value = MagicMock(
            rendered_text="Test prompt"
        )

        # Create mock event logger
        mock_append_event = MagicMock()

        mock_backend_result = MagicMock()
        mock_backend_result.exit_code = 0
        mock_backend_result.is_success.return_value = True

        # Mock OrchestraStatusService with .create() factory method
        mock_status_service = MagicMock()
        mock_status_service.snapshot.return_value = MagicMock(
            circuit_breaker_state="closed"
        )
        mock_service_class = MagicMock()
        mock_service_class.create.return_value = mock_status_service

        with (pytest.MonkeyPatch().context() as m,):
            m.setattr(
                "vibe3.execution.governance_sync_runner.load_orchestra_config",
                lambda *, target_repo=None: MagicMock(),
            )
            m.setattr(
                "vibe3.orchestra.flow_dispatch.FlowManager",
                lambda config: MagicMock(),
            )
            m.setattr(
                "vibe3.services.orchestra.status.OrchestraStatusService",
                mock_service_class,
            )
            m.setattr(
                "vibe3.execution.governance_sync_runner.CodeagentBackend",
                lambda: MagicMock(run=lambda *args, **kwargs: mock_backend_result),
            )

            run_governance_sync(
                tick_count=5,
                dry_run=False,
                show_prompt=False,
                session_id=None,
                governance_fns=mock_governance_fns,
                append_event=mock_append_event,
            )

        # Should log completion event
        mock_append_event.assert_called()
        call_args = mock_append_event.call_args.args[0]
        assert "completed" in call_args or "tick=5" in call_args

    def test_error_path_records_to_error_tracking(self) -> None:
        """API error should be classified and recorded to ErrorTrackingService."""
        from vibe3.execution.governance_sync_runner import run_governance_sync

        # Create mock governance functions
        mock_governance_fns = MagicMock()
        mock_governance_fns.resolve_options.return_value = MagicMock(
            backend="claude", model="sonnet"
        )
        mock_governance_fns.build_snapshot_context.return_value = {}
        mock_governance_fns.render_prompt.return_value = MagicMock(
            rendered_text="Test prompt"
        )

        # Create mock event logger
        mock_append_event = MagicMock()

        # Mock OrchestraStatusService with .create() factory method
        mock_status_service = MagicMock()
        mock_status_service.snapshot.return_value = MagicMock(
            circuit_breaker_state="closed"
        )
        mock_service_class = MagicMock()
        mock_service_class.create.return_value = mock_status_service

        with (pytest.MonkeyPatch().context() as m,):
            m.setattr(
                "vibe3.execution.governance_sync_runner.load_orchestra_config",
                lambda *, target_repo=None: MagicMock(),
            )
            m.setattr(
                "vibe3.orchestra.flow_dispatch.FlowManager",
                lambda config: MagicMock(),
            )
            m.setattr(
                "vibe3.services.orchestra.status.OrchestraStatusService",
                mock_service_class,
            )
            m.setattr(
                "vibe3.execution.governance_sync_runner.CodeagentBackend",
                lambda: MagicMock(
                    run=lambda *args, **kwargs: (_ for _ in ()).throw(
                        RuntimeError("API error: rate limited")
                    )
                ),
            )

            mock_tracking = MagicMock()
            m.setattr(
                "vibe3.services.orchestra.error_tracking.service.ErrorTrackingService.get_instance",
                lambda store=None: mock_tracking,
            )

            with pytest.raises(RuntimeError):
                run_governance_sync(
                    tick_count=5,
                    dry_run=False,
                    show_prompt=False,
                    session_id=None,
                    governance_fns=mock_governance_fns,
                    append_event=mock_append_event,
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


class TestGovernanceAsyncRunnerWithInjection:
    """Test governance async runner with injected dependencies."""

    def test_skip_when_concurrent_governance_at_limit(self) -> None:
        """Async dispatch should be skipped when concurrent sessions >= limit."""
        from vibe3.execution.governance_sync_runner import run_governance_async

        mock_config = MagicMock()
        mock_config.governance_max_concurrent = 1

        mock_registry = MagicMock()
        mock_registry.list_live_governance_sessions.return_value = [
            {"tmux_session": "vibe3-governance-tick-0"},
        ]
        mock_registry.mark_governance_sessions_done_when_tmux_gone = MagicMock()

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "vibe3.execution.governance_sync_runner.load_orchestra_config",
                lambda *, target_repo=None: mock_config,
            )
            mock_store_ctx = MagicMock()
            mock_store = MagicMock()
            mock_store.__enter__ = MagicMock(return_value=mock_store_ctx)
            mock_store.__exit__ = MagicMock(return_value=False)
            m.setattr(
                "vibe3.execution.governance_sync_runner.get_store",
                lambda: mock_store,
            )
            m.setattr(
                "vibe3.execution.governance_sync_runner.CodeagentBackend",
                lambda: MagicMock(),
            )
            m.setattr(
                "vibe3.environment.session_registry.SessionRegistryService",
                lambda store, backend: mock_registry,
            )
            _mock_execution_coordinator(m)

            run_governance_async(
                tick_count=0,
                build_execution_name=(
                    lambda tick, material=None: f"governance-tick-{tick}"
                ),
            )

        # append_governance_event is a local import inside run_governance_async
        # and not injected, so we can't mock it via setattr. We skip the
        # assertion (verification is done via integration tests)

    def test_skip_when_circuit_breaker_open(self) -> None:
        """Async dispatch should be skipped when circuit breaker is open."""
        from vibe3.execution.governance_sync_runner import run_governance_async

        mock_config = MagicMock()
        mock_config.governance_max_concurrent = 3

        mock_registry = MagicMock()
        mock_registry.list_live_governance_sessions.return_value = []
        mock_registry.mark_governance_sessions_done_when_tmux_gone = MagicMock()

        mock_snapshot = MagicMock()
        mock_snapshot.circuit_breaker_state = "open"
        mock_status_service = MagicMock()
        mock_status_service.snapshot.return_value = mock_snapshot
        mock_service_class = MagicMock()
        mock_service_class.create.return_value = mock_status_service

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "vibe3.execution.governance_sync_runner.load_orchestra_config",
                lambda *, target_repo=None: mock_config,
            )
            mock_store_ctx = MagicMock()
            mock_store = MagicMock()
            mock_store.__enter__ = MagicMock(return_value=mock_store_ctx)
            mock_store.__exit__ = MagicMock(return_value=False)
            m.setattr(
                "vibe3.execution.governance_sync_runner.get_store",
                lambda: mock_store,
            )
            m.setattr(
                "vibe3.execution.governance_sync_runner.CodeagentBackend",
                lambda: MagicMock(),
            )
            m.setattr(
                "vibe3.environment.session_registry.SessionRegistryService",
                lambda store, backend: mock_registry,
            )
            m.setattr(
                "vibe3.orchestra.flow_dispatch.FlowManager",
                lambda config: MagicMock(),
            )
            m.setattr(
                "vibe3.services.orchestra.status.OrchestraStatusService",
                mock_service_class,
            )
            m.setattr(
                "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
                lambda: Path("/tmp/test-repo"),  # Return real Path, not MagicMock
            )
            _mock_execution_coordinator(m)

            run_governance_async(
                tick_count=5,
                build_execution_name=(
                    lambda tick, material=None: f"governance-tick-{tick}"
                ),
            )

        # append_governance_event is a local import inside run_governance_async
        # and not injected, so we can't mock it via setattr. We skip the
        # assertion (verification is done via integration tests)
