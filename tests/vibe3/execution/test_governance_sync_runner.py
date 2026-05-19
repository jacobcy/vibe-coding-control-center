"""Tests for governance_sync_runner error tracking integration.

Verifies API errors in governance sync execution path are captured
by ErrorTrackingService for FailedGate threshold checking.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestGovernanceSyncRunner:
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
        mock_backend.run.side_effect = RuntimeError("API error: rate limited")
        mock_backend_cls.return_value = mock_backend

        with patch(
            "vibe3.exceptions.error_tracking.ErrorTrackingService"
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

            mock_tracking.record_error.assert_called_once()
            call_args = mock_tracking.record_error.call_args
            assert call_args.kwargs["error_code"] == "E_API_RATE_LIMIT"
            assert call_args.kwargs["tick_id"] == 5
            assert call_args.kwargs["issue_number"] is None
            assert call_args.kwargs["branch"] is None

        mock_append_event.assert_called()
