"""Comprehensive unit tests for orchestra_log.py."""

import os
from pathlib import Path

import pytest

import vibe3.observability.orchestra_log as mod


@pytest.fixture(autouse=True)
def reset_global_handle():
    """Reset module-level globals before and after each test."""
    mod._events_handle = None
    mod._events_path = None
    # Clean environment variables
    for key in [
        "VIBE3_ORCHESTRA_EVENT_LOG",
        "VIBE3_ORCHESTRA_LOG_LEVEL",
        "VIBE3_ASYNC_LOG_DIR",
    ]:
        os.environ.pop(key, None)
    yield
    # Teardown: close any open handles and reset
    mod._close_events_log()
    mod._events_handle = None
    mod._events_path = None
    for key in [
        "VIBE3_ORCHESTRA_EVENT_LOG",
        "VIBE3_ORCHESTRA_LOG_LEVEL",
        "VIBE3_ASYNC_LOG_DIR",
    ]:
        os.environ.pop(key, None)


@pytest.fixture
def enable_event_log(monkeypatch):
    """Enable event logging via environment variable."""
    monkeypatch.setenv("VIBE3_ORCHESTRA_EVENT_LOG", "1")


# Step 2: Test directory resolution functions (4 tests)


def test_orchestra_log_dir_default(tmp_path: Path):
    """orchestra_log_dir returns tmp_path / temp / logs / orchestra and creates it."""
    result = mod.orchestra_log_dir(repo_root=tmp_path)
    assert result == tmp_path / "temp" / "logs" / "orchestra"
    assert result.exists()
    assert result.is_dir()


def test_orchestra_log_dir_env_override(tmp_path: Path, monkeypatch):
    """orchestra_log_dir returns override_dir / orchestra.

    Tests that VIBE3_ASYNC_LOG_DIR environment variable overrides the default path.
    """
    override_dir = tmp_path / "custom_logs"
    monkeypatch.setenv("VIBE3_ASYNC_LOG_DIR", str(override_dir))

    result = mod.orchestra_log_dir(repo_root=tmp_path)
    assert result == override_dir / "orchestra"
    assert result.exists()
    assert result.is_dir()


def test_governance_log_dir_and_events_path(tmp_path: Path):
    """governance_log_dir returns subdirectory under orchestra dir.

    governance_events_log_path returns governance.log inside the governance directory.
    """
    orchestra_dir = mod.orchestra_log_dir(repo_root=tmp_path)
    governance_dir = mod.governance_log_dir(repo_root=tmp_path)

    assert governance_dir == orchestra_dir / "governance"
    assert governance_dir.exists()
    assert governance_dir.is_dir()

    events_path = mod.governance_events_log_path(repo_root=tmp_path)
    assert events_path == governance_dir / "governance.log"


def test_governance_dry_run_dir(tmp_path: Path):
    """governance_dry_run_dir returns orchestra_log_dir / governance / dry-run.

    The directory is created if it doesn't exist.
    """
    result = mod.governance_dry_run_dir(repo_root=tmp_path)
    orchestra_dir = mod.orchestra_log_dir(repo_root=tmp_path)

    assert result == orchestra_dir / "governance" / "dry-run"
    assert result.exists()
    assert result.is_dir()


# Step 3: Test persistent handle lifecycle (5 tests)


def test_ensure_events_handle_opens_file(tmp_path: Path, enable_event_log):
    """_ensure_events_handle opens file and sets _events_handle and _events_path."""
    handle = mod._ensure_events_handle(repo_root=tmp_path)

    assert mod._events_handle is not None
    assert mod._events_handle is handle
    assert mod._events_path is not None
    assert mod._events_path == tmp_path / "temp" / "logs" / "orchestra" / "events.log"
    assert mod._events_path.exists()


def test_ensure_events_handle_reuses_same_path(tmp_path: Path, enable_event_log):
    """_ensure_events_handle reuses the same handle when called twice.

    The handle is reused when called with the same repo_root.
    """
    handle1 = mod._ensure_events_handle(repo_root=tmp_path)
    handle2 = mod._ensure_events_handle(repo_root=tmp_path)

    assert handle1 is handle2
    assert mod._events_handle is handle1


def test_ensure_events_handle_reopens_on_path_change(tmp_path: Path, enable_event_log):
    """_ensure_events_handle reopens when repo_root changes, closing old handle."""
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    repo_a.mkdir()
    repo_b.mkdir()

    handle_a = mod._ensure_events_handle(repo_root=repo_a)
    path_a = mod._events_path

    handle_b = mod._ensure_events_handle(repo_root=repo_b)
    path_b = mod._events_path

    assert handle_a is not handle_b
    assert mod._events_handle is handle_b
    assert path_a != path_b
    assert path_b == repo_b / "temp" / "logs" / "orchestra" / "events.log"


def test_close_events_log(enable_event_log, tmp_path: Path):
    """_close_events_log resets _events_handle and _events_path to None."""
    mod._ensure_events_handle(repo_root=tmp_path)
    assert mod._events_handle is not None
    assert mod._events_path is not None

    mod._close_events_log()

    assert mod._events_handle is None
    assert mod._events_path is None


def test_close_events_log_handles_exception(
    enable_event_log, tmp_path: Path, monkeypatch
):
    """_close_events_log handles OSError gracefully and resets globals."""
    mod._ensure_events_handle(repo_root=tmp_path)
    assert mod._events_handle is not None

    # Monkeypatch the close method to raise OSError
    original_handle = mod._events_handle

    def raise_os_error():
        raise OSError("Mocked close failure")

    monkeypatch.setattr(original_handle, "close", raise_os_error)

    # Should not raise
    mod._close_events_log()

    # Should still reset globals
    assert mod._events_handle is None
    assert mod._events_path is None


# Step 4: Test append_orchestra_event with level filtering (6 tests)


def test_append_event_disabled(tmp_path: Path):
    """append_orchestra_event returns path but writes nothing when disabled.

    VIBE3_ORCHESTRA_EVENT_LOG is not set, so no I/O should occur.
    """
    result = mod.append_orchestra_event("component", "message", repo_root=tmp_path)

    expected_path = tmp_path / "temp" / "logs" / "orchestra" / "events.log"
    assert result == expected_path
    assert not expected_path.exists()


def test_append_event_writes_formatted_line(tmp_path: Path, enable_event_log):
    """append_orchestra_event writes [timestamp] [component] message format."""
    result = mod.append_orchestra_event(
        "test_component", "test message", repo_root=tmp_path
    )

    assert result.exists()
    content = result.read_text()
    assert "[test_component] test message\n" in content
    # Check timestamp format
    assert len(content) > 0
    lines = content.strip().split("\n")
    assert len(lines) == 1
    # Format: [YYYY-MM-DDTHH:MM:SS] [component] message
    assert lines[0].startswith("[")
    assert "] [test_component] test message" in lines[0]


def test_append_event_empty_message(tmp_path: Path, enable_event_log):
    """append_orchestra_event writes just newline when message is empty."""
    result = mod.append_orchestra_event("component", "", repo_root=tmp_path)

    assert result.exists()
    content = result.read_text()
    assert content == "\n"


def test_append_event_level_filter_default_info(tmp_path: Path, enable_event_log):
    """Default VIBE3_ORCHESTRA_LOG_LEVEL=INFO filters out DEBUG events."""
    # Write INFO event
    mod.append_orchestra_event("comp", "info message", level="INFO", repo_root=tmp_path)

    # Try to write DEBUG event (should be filtered)
    mod.append_orchestra_event(
        "comp", "debug message", level="DEBUG", repo_root=tmp_path
    )

    content = mod._events_path.read_text()
    assert "info message" in content
    assert "debug message" not in content


def test_append_event_level_filter_warning(
    tmp_path: Path, enable_event_log, monkeypatch
):
    """VIBE3_ORCHESTRA_LOG_LEVEL=WARNING filters INFO but not WARNING or ERROR."""
    monkeypatch.setenv("VIBE3_ORCHESTRA_LOG_LEVEL", "WARNING")

    # These should be filtered
    mod.append_orchestra_event("comp", "debug", level="DEBUG", repo_root=tmp_path)
    mod.append_orchestra_event("comp", "info", level="INFO", repo_root=tmp_path)

    # These should be written
    mod.append_orchestra_event("comp", "warning", level="WARNING", repo_root=tmp_path)
    mod.append_orchestra_event("comp", "error", level="ERROR", repo_root=tmp_path)

    content = mod._events_path.read_text()
    assert "debug" not in content
    assert "info" not in content
    assert "warning" in content
    assert "error" in content


def test_append_event_level_filter_debug(tmp_path: Path, enable_event_log, monkeypatch):
    """VIBE3_ORCHESTRA_LOG_LEVEL=DEBUG writes all levels."""
    monkeypatch.setenv("VIBE3_ORCHESTRA_LOG_LEVEL", "DEBUG")

    mod.append_orchestra_event("comp", "debug", level="DEBUG", repo_root=tmp_path)
    mod.append_orchestra_event("comp", "info", level="INFO", repo_root=tmp_path)
    mod.append_orchestra_event("comp", "warning", level="WARNING", repo_root=tmp_path)
    mod.append_orchestra_event("comp", "error", level="ERROR", repo_root=tmp_path)

    content = mod._events_path.read_text()
    assert "debug" in content
    assert "info" in content
    assert "warning" in content
    assert "error" in content


# Step 5: Test append_orchestra_run_separator (2 tests)


def test_run_separator_disabled(tmp_path: Path):
    """append_orchestra_run_separator returns path but writes nothing when disabled."""
    result = mod.append_orchestra_run_separator(repo_root=tmp_path)

    expected_path = tmp_path / "temp" / "logs" / "orchestra" / "events.log"
    assert result == expected_path
    assert not expected_path.exists()


def test_run_separator_writes_separator(tmp_path: Path, enable_event_log):
    """append_orchestra_run_separator writes formatted separator line."""
    result = mod.append_orchestra_run_separator(
        title="custom title", repo_root=tmp_path
    )

    assert result.exists()
    content = result.read_text()
    assert "========== custom title @ " in content
    assert " ==========\n" in content


# Step 6: Test append_governance_event dual logging (3 tests)


def test_governance_event_writes_to_both_files(tmp_path: Path, enable_event_log):
    """append_governance_event writes to both governance.log and events.log."""
    result = mod.append_governance_event("governance message", repo_root=tmp_path)

    # Check governance.log
    assert result.exists()
    governance_content = result.read_text()
    assert "governance message" in governance_content

    # Check events.log (via delegation to append_orchestra_event)
    events_path = tmp_path / "temp" / "logs" / "orchestra" / "events.log"
    assert events_path.exists()
    events_content = events_path.read_text()
    assert "governance message" in events_content
    assert "[governance] governance message" in events_content


def test_governance_event_creates_governance_dir(tmp_path: Path):
    """append_governance_event creates governance/ directory.

    The directory is created even when event log is disabled.
    """
    result = mod.append_governance_event("test message", repo_root=tmp_path)

    governance_dir = tmp_path / "temp" / "logs" / "orchestra" / "governance"
    assert governance_dir.exists()
    assert result.parent == governance_dir


def test_governance_event_format(tmp_path: Path, enable_event_log):
    """append_governance_event writes [timestamp] message format to governance.log."""
    result = mod.append_governance_event("test message", repo_root=tmp_path)

    content = result.read_text()
    assert "test message\n" in content
    # Check that it doesn't include [component] like events.log does
    assert "[governance]" not in content
    # But it should have a timestamp
    assert content.startswith("[")
