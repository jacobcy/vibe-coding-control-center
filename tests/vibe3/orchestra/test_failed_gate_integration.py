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
                reason="Model configuration errors: E_MODEL_NOT_FOUND",
                blocked_ticks=0,
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
            assert "blocked by failed gate" in output
            assert "Model configuration errors" in output
            assert "vibe3 serve resume" in output


@pytest.mark.asyncio
async def test_heartbeat_tick_blocked_by_active_gate() -> None:
    """Heartbeat runtime should skip on_tick() when FailedGate is ACTIVE."""
    config = OrchestraConfig(polling_interval=1)
    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult(blocked=True, reason="Blocked")

    server = HeartbeatServer(config, failed_gate=mock_gate)
    tick_calls: list[str] = []

    class TickService:
        service_name = "tick-service"
        event_types: list[str] = []
        is_dispatch_service = True

        async def on_tick(self) -> None:
            tick_calls.append("tick")

    server.register(TickService())
    server._running = True

    call_count = 0

    async def _no_wait(_seconds: float) -> None:
        nonlocal call_count
        call_count += 1
        # First sleep: let gate check execute
        # Second sleep: stop server to exit loop
        if call_count >= 2:
            server.stop()

    with patch("vibe3.runtime.heartbeat.asyncio.sleep", _no_wait):
        await server._tick_loop()

    # Gate is ACTIVE → on_tick skipped, blocked_ticks incremented
    assert tick_calls == []
    mock_gate.increment_blocked_ticks.assert_called_once()


@pytest.mark.asyncio
async def test_event_dispatch_not_blocked_by_failed_gate() -> None:
    """Heartbeat runtime should ignore FailedGate and keep dispatching."""
    config = OrchestraConfig()
    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult(blocked=True, reason="Blocked")

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
    mock_gate.check.return_value = GateResult(blocked=True, reason="Blocked")

    server = HeartbeatServer(config, failed_gate=mock_gate)
    svc = NonDispatchService()
    svc.handle_event = MagicMock(side_effect=asyncio.Future)  # type: ignore[method-assign]
    svc.handle_event.return_value.set_result(None)
    server.register(svc)

    event = GitHubEvent(event_type="issue_comment", action="created", payload={})
    await server._dispatch_event(event)

    # handle_event SHOULD have been called
    svc.handle_event.assert_called_once_with(event)
