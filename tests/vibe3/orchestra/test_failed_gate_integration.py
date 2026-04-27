"""Integration tests for FailedGate orchestration blocking."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.runtime.service_protocol import GitHubEvent
from vibe3.server.app import app


def test_serve_start_preflight_blocked() -> None:
    """serve start should fail if FailedGate reports blocked."""
    with patch("vibe3.server.app.load_orchestra_config") as mock_cfg:
        mock_cfg.return_value = OrchestraConfig(enabled=True)

        with patch("vibe3.orchestra.failed_gate.FailedGate.check") as mock_check:
            mock_check.return_value = GateResult(
                blocked=True,
                issue_number=123,
                issue_title="Broken",
                reason="System down",
            )

            runner = CliRunner()
            # We need to mock setup_logging to avoid side effects
            with patch("vibe3.server.app.setup_logging"):
                # Mock _validate_pid_file to say no process running
                with patch("vibe3.server.app._validate_pid_file") as mock_pid:
                    mock_pid.return_value = (None, False)
                    with patch("vibe3.server.app.ensure_port_available"):
                        result = runner.invoke(app, ["start"])

            assert result.exit_code == 1
            output = result.output  # Combined stdout + stderr
            assert "blocked by open state/failed issue" in output
            assert "issue:  #123" in output
            assert "reason: System down" in output
            assert "transition it back to state/handoff" in output


@pytest.mark.asyncio
async def test_heartbeat_tick_not_blocked_by_failed_gate() -> None:
    """Heartbeat runtime should ignore FailedGate and keep ticking."""
    config = OrchestraConfig(polling_interval=1)
    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult(
        blocked=True, issue_number=123, reason="Blocked"
    )

    server = HeartbeatServer(config, failed_gate=mock_gate)
    tick_calls: list[str] = []

    class TickService:
        service_name = "tick-service"
        event_types = []
        is_dispatch_service = True

        async def on_tick(self) -> None:
            tick_calls.append("tick")
            server.stop()

    server.register(TickService())
    server._running = True

    async def _no_wait(_seconds: float) -> None:
        return None

    with patch("vibe3.runtime.heartbeat.asyncio.sleep", _no_wait):
        await server._tick_loop()

    assert tick_calls == ["tick"]


@pytest.mark.asyncio
async def test_event_dispatch_not_blocked_by_failed_gate() -> None:
    """Heartbeat runtime should ignore FailedGate and keep dispatching."""
    config = OrchestraConfig()
    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult(
        blocked=True, issue_number=123, reason="Blocked"
    )

    server = HeartbeatServer(config, failed_gate=mock_gate)
    mock_service = MagicMock()
    mock_service.event_types = ["push"]
    server.register(mock_service)

    event = GitHubEvent(event_type="push", action="created", payload={})
    await server._dispatch_event(event)

    mock_service.handle_event.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_event_dispatch_not_blocked_for_non_dispatchers() -> None:
    """Non-dispatching services continue processing events."""
    from vibe3.runtime.service_protocol import ServiceBase

    class NonDispatchService(ServiceBase):
        event_types = ["issue_comment"]

        @property
        def is_dispatch_service(self) -> bool:
            return False

        async def handle_event(self, event: GitHubEvent) -> None:
            pass

    config = OrchestraConfig()
    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult(
        blocked=True, issue_number=123, reason="Blocked"
    )

    server = HeartbeatServer(config, failed_gate=mock_gate)
    svc = NonDispatchService()
    svc.handle_event = MagicMock(side_effect=asyncio.Future)
    svc.handle_event.return_value.set_result(None)
    server.register(svc)

    event = GitHubEvent(event_type="issue_comment", action="created", payload={})
    await server._dispatch_event(event)

    # handle_event SHOULD have been called
    svc.handle_event.assert_called_once_with(event)
