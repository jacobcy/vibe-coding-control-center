"""Tests for FailedGate module (SQLite-based implementation)."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.clients import SQLiteClient
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import FailedGate, GateResult
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.server.app import app
from vibe3.services.error_tracking_service import ErrorTrackingService


@pytest.fixture(autouse=True)
def reset_error_tracking() -> Iterator[None]:
    """Reset ErrorTrackingService singleton between tests."""
    yield
    db_paths = [i.db_path for i in ErrorTrackingService._registry.values()]
    if ErrorTrackingService._instance:
        db_paths.append(ErrorTrackingService._instance.db_path)
    if ErrorTrackingService._default_instance:
        db_paths.append(ErrorTrackingService._default_instance.db_path)
    ErrorTrackingService.clear_instance()
    for db_path in set(db_paths):
        # Only handle "no such table" errors - these occur when the DB file
        # was deleted by concurrent test cleanup. Other errors should propagate.
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM error_log")
                conn.execute(
                    "UPDATE failed_gate_state SET is_active = 0, "
                    "reason = NULL, triggered_at = NULL, blocked_ticks = 0 WHERE id = 1"
                )
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e):
                raise


@pytest.fixture
def temp_store(tmp_path: Path) -> SQLiteClient:
    """Create a temporary SQLiteClient for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from vibe3.clients import init_schema

    init_schema(conn)
    conn.close()
    return SQLiteClient(db_path=str(db_path))


def test_failed_gate_open(temp_store: SQLiteClient) -> None:
    """Gate should be open when no errors are recorded."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)
    result = gate.check()
    assert not result.blocked
    assert result.reason is None


def test_failed_gate_blocked_by_model_error(temp_store: SQLiteClient) -> None:
    """Gate should block immediately on model config errors."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    ErrorTrackingService._instance.record_error("E_MODEL_NOT_FOUND", "Model not found")
    gate = FailedGate(store=temp_store)
    result = gate.check()
    assert result.blocked
    assert "CRITICAL" in (result.reason or "")


def test_failed_gate_blocked_by_api_threshold(temp_store: SQLiteClient) -> None:
    """Gate should block when ERROR-severity error threshold is reached."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT", "Rate limit", tick_id=1
    )
    ErrorTrackingService._instance.record_error("E_API_TIMEOUT", "Timeout", tick_id=2)
    gate = FailedGate(store=temp_store)
    result = gate.check()
    assert result.blocked
    assert "ERROR-severity threshold" in (result.reason or "")


def test_failed_gate_clear(temp_store: SQLiteClient) -> None:
    """Gate should clear and allow operation after manual resume."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    ErrorTrackingService._instance.record_error("E_MODEL_NOT_FOUND", "Model error")
    gate = FailedGate(store=temp_store)
    result = gate.check()
    assert result.blocked
    gate.clear(cleared_by="admin:manual", reason="Fixed model config")
    result = gate.check()
    assert not result.blocked


def test_failed_gate_persists_state(temp_store: SQLiteClient) -> None:
    """Gate state should persist across instances."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    ErrorTrackingService._instance.record_error(
        "E_MODEL_PERMISSION", "Permission denied"
    )
    gate1 = FailedGate(store=temp_store)
    result1 = gate1.check()
    assert result1.blocked
    gate2 = FailedGate(store=temp_store)
    result2 = gate2.check()
    assert result2.blocked
    assert result2.reason == result1.reason


def test_failed_gate_increment_blocked_ticks(temp_store: SQLiteClient) -> None:
    """Gate should increment blocked_ticks when active."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    ErrorTrackingService._instance.record_error("E_MODEL_CONFIG", "Config error")
    gate = FailedGate(store=temp_store)
    result = gate.check()
    assert result.blocked
    assert result.blocked_ticks == 0
    gate.increment_blocked_ticks()
    gate.increment_blocked_ticks()
    status = gate.get_status()
    assert status.blocked_ticks == 2


def test_per_db_path_instance_isolation(tmp_path: Path) -> None:
    """Different db_path instances should be isolated."""
    db_path1 = tmp_path / "test1.db"
    db_path2 = tmp_path / "test2.db"
    for db_path in [db_path1, db_path2]:
        conn = sqlite3.connect(db_path)
        from vibe3.clients import init_schema

        init_schema(conn)
        conn.close()
    store1 = SQLiteClient(db_path=str(db_path1))
    store2 = SQLiteClient(db_path=str(db_path2))
    instance1 = ErrorTrackingService.get_instance(store=store1)
    instance2 = ErrorTrackingService.get_instance(store=store2)
    assert instance1 is not instance2
    assert instance1.db_path != instance2.db_path
    instance1.record_error("E_MODEL_TEST", "Test error in db1")
    assert instance1.has_model_config_error()
    assert not instance2.has_model_config_error()
    ErrorTrackingService.clear_instance(db_path=str(db_path1))
    instance1_new = ErrorTrackingService.get_instance(store=store1)
    assert instance1_new.has_model_config_error()
    assert not instance2.has_model_config_error()


def test_clear_instance_specific_db_path(tmp_path: Path) -> None:
    """clear_instance(db_path) should only clear that instance."""
    db_path1 = tmp_path / "test1.db"
    db_path2 = tmp_path / "test2.db"
    for db_path in [db_path1, db_path2]:
        conn = sqlite3.connect(db_path)
        from vibe3.clients import init_schema

        init_schema(conn)
        conn.close()
    store1 = SQLiteClient(db_path=str(db_path1))
    store2 = SQLiteClient(db_path=str(db_path2))
    instance1 = ErrorTrackingService.get_instance(store=store1)
    instance2 = ErrorTrackingService.get_instance(store=store2)
    instance1.record_error("E_API_TEST1", "Error 1")
    instance2.record_error("E_API_TEST2", "Error 2")
    ErrorTrackingService.clear_instance(db_path=str(db_path1))
    instance1_new = ErrorTrackingService.get_instance(store=store1)
    instance2_new = ErrorTrackingService.get_instance(store=store2)
    assert instance1_new.get_api_error_count() == 1
    assert instance2_new.get_api_error_count() == 1
    assert instance2_new is instance2


def test_clear_instance_with_db_path_clears_matching_singleton(tmp_path: Path) -> None:
    """clear_instance(db_path) should also clear _instance if it matches."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from vibe3.clients import init_schema

    init_schema(conn)
    conn.close()
    store = SQLiteClient(db_path=str(db_path))
    ErrorTrackingService._instance = ErrorTrackingService(store=store)
    assert ErrorTrackingService._instance is not None
    assert ErrorTrackingService._instance.db_path == str(db_path)
    ErrorTrackingService.clear_instance(db_path=str(db_path))
    assert (
        ErrorTrackingService._instance is None
    ), "clear_instance(db_path) should clear _instance if db_path matches"


def test_get_instance_with_and_without_store(tmp_path: Path) -> None:
    """get_instance() without store should return default instance."""
    ErrorTrackingService.clear_instance()
    default_instance = ErrorTrackingService.get_instance()
    assert default_instance is not None
    default_instance2 = ErrorTrackingService.get_instance()
    assert default_instance is default_instance2
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from vibe3.clients import init_schema

    init_schema(conn)
    conn.close()
    store = SQLiteClient(db_path=str(db_path))
    custom_instance = ErrorTrackingService.get_instance(store=store)
    assert custom_instance is not default_instance
    assert custom_instance.db_path != default_instance.db_path
    ErrorTrackingService.clear_instance()
    default_instance3 = ErrorTrackingService.get_instance()
    assert default_instance3 is not default_instance
    custom_instance2 = ErrorTrackingService.get_instance(store=store)
    assert (
        custom_instance2 is not custom_instance
    ), "clear_instance() should clear _registry to prevent test leakage"


def test_warning_does_not_close_gate(temp_store: SQLiteClient) -> None:
    """Test that WARNING severity errors don't close the gate."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)
    for i in range(5):
        ErrorTrackingService.get_instance().record_error(
            error_code="E_EXEC_NO_OUTPUT",
            error_message=f"No output {i}",
        )
    result = gate.check()
    assert not result.blocked, "Gate should not close for WARNING errors"


def test_critical_closes_gate_immediately(temp_store: SQLiteClient) -> None:
    """Test that CRITICAL severity closes gate immediately."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)
    ErrorTrackingService.get_instance().record_error(
        error_code="E_MODEL_NOT_FOUND",
        error_message="Model not found",
    )
    result = gate.check()
    assert result.blocked, "Gate should close immediately for CRITICAL"
    assert "CRITICAL" in (result.reason or "")


class TestFailedGateIntegration:
    """Integration tests for FailedGate orchestration blocking."""

    def test_serve_start_preflight_blocked(self, temp_store: SQLiteClient) -> None:
        """serve start should fail if FailedGate reports blocked."""
        ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
        with patch("vibe3.server.app.load_orchestra_config") as mock_cfg:
            mock_cfg.return_value = OrchestraConfig(enabled=True)
            with patch("vibe3.orchestra.failed_gate.FailedGate.check") as mock_check:
                mock_check.return_value = GateResult(
                    blocked=True,
                    reason="Model configuration errors: E_MODEL_NOT_FOUND",
                    blocked_ticks=0,
                )
                runner = CliRunner()
                with patch("vibe3.server.app.setup_logging"):
                    with patch("vibe3.server.app._validate_pid_file") as mock_pid:
                        mock_pid.return_value = (None, False)
                        with patch(
                            "vibe3.server.app.find_available_port",
                            lambda port, max_port: (port, False),
                        ):
                            result = runner.invoke(app, ["start"])
                assert result.exit_code == 1
                output = result.output
                assert "blocked by failed gate" in output
                assert "Model configuration errors" in output
                assert "vibe3 serve resume" in output

    @pytest.mark.asyncio
    async def test_heartbeat_tick_blocked_by_active_gate(
        self, temp_store: SQLiteClient
    ) -> None:
        """Heartbeat runtime should skip on_tick() when FailedGate is ACTIVE."""
        ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
        config = OrchestraConfig(polling_interval=1)
        mock_gate = MagicMock()
        mock_gate.check.return_value = GateResult(blocked=True, reason="Blocked")
        server = HeartbeatServer(config, failed_gate=mock_gate)
        tick_calls: list[str] = []

        class TickService:
            service_name = "tick-service"
            is_dispatch_service = True

            async def on_tick(self, tick_id: int = 0) -> None:
                tick_calls.append("tick")

        server.register(TickService())
        server._running = True
        call_count = 0

        async def _no_wait(_seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                server.stop()

        with patch("vibe3.runtime.heartbeat.asyncio.sleep", _no_wait):
            await server._tick_loop()
        assert tick_calls == []
        mock_gate.increment_blocked_ticks.assert_called_once()

    def test_end_to_end_gate_activation_from_threshold_errors(
        self, temp_store: SQLiteClient
    ) -> None:
        """End-to-end test: governance errors → gate activation (threshold reached).

        Note: This test verifies FailedGate activation behavior. For heartbeat
        blocking behavior, see test_heartbeat_tick_blocked_by_active_gate().
        """
        from vibe3.exceptions.error_severity import ErrorSeverity

        ErrorTrackingService.clear_instance()
        default_instance = ErrorTrackingService.get_instance(store=temp_store)
        default_instance.record_error(
            error_code="E_API_RATE_LIMIT",
            error_message="Rate limit exceeded",
            tick_id=1,
            severity=ErrorSeverity.ERROR,
        )
        default_instance.record_error(
            error_code="E_API_TIMEOUT",
            error_message="API timeout",
            tick_id=2,
            severity=ErrorSeverity.ERROR,
        )
        gate = FailedGate(store=temp_store)
        result = gate.check()
        assert result.blocked, "Gate should be blocked after 2 ERROR-severity errors"
        assert "ERROR-severity threshold" in (result.reason or "")
        status = gate.get_status()
        assert status.is_active, "Gate should be ACTIVE after threshold reached"
        assert status.blocked_ticks == 0, "No ticks counted yet"
