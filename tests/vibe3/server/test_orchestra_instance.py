"""Tests for orchestra instance info management."""

from datetime import datetime
from pathlib import Path

from vibe3.server.orchestra_instance import (
    OrchestraInstanceInfo,
    read_instance_info,
    write_instance_info,
)


def test_write_and_read_instance_info(tmp_path: Path) -> None:
    """Test write/read roundtrip for instance info."""
    pid_file = tmp_path / "orchestra.pid"
    info = OrchestraInstanceInfo(
        pid=12345,
        cwd=Path("/Users/test/project-a"),
        port=8080,
        started_at=datetime(2026, 5, 30, 9, 35, 0),
    )

    write_instance_info(pid_file, info)
    result = read_instance_info(pid_file)

    assert result is not None
    assert result.pid == 12345
    assert result.cwd == Path("/Users/test/project-a")
    assert result.port == 8080
    assert result.started_at == datetime(2026, 5, 30, 9, 35, 0)


def test_read_invalid_json(tmp_path: Path) -> None:
    """Test reading corrupted JSON returns None."""
    pid_file = tmp_path / "orchestra.pid"
    pid_file.write_text("not valid json {")

    result = read_instance_info(pid_file)

    assert result is None


def test_read_missing_file(tmp_path: Path) -> None:
    """Test reading missing file returns None."""
    pid_file = tmp_path / "nonexistent.pid"

    result = read_instance_info(pid_file)

    assert result is None


def test_read_invalid_format(tmp_path: Path) -> None:
    """Test reading file with missing required fields returns None."""
    pid_file = tmp_path / "orchestra.pid"
    pid_file.write_text('{"pid": 12345}')  # Missing cwd, port, started_at

    result = read_instance_info(pid_file)

    assert result is None
