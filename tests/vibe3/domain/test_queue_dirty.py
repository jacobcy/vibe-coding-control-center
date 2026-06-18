"""Tests for queue_dirty signal management."""

from pathlib import Path

from vibe3.domain.queue_dirty import (
    clear_queue_dirty,
    is_queue_dirty,
    mark_queue_dirty,
)


def test_mark_queue_dirty_creates_file(tmp_path: Path) -> None:
    """Test that mark_queue_dirty creates the marker file."""
    git_common_dir = str(tmp_path)

    mark_queue_dirty(git_common_dir)

    marker_path = tmp_path / "vibe3" / "queue_dirty"
    assert marker_path.exists()


def test_is_queue_dirty_returns_false_when_no_marker(tmp_path: Path) -> None:
    """Test that is_queue_dirty returns False when marker doesn't exist."""
    git_common_dir = str(tmp_path)

    result = is_queue_dirty(git_common_dir)

    assert result is False


def test_is_queue_dirty_returns_true_after_mark(tmp_path: Path) -> None:
    """Test that is_queue_dirty returns True after marking."""
    git_common_dir = str(tmp_path)

    mark_queue_dirty(git_common_dir)
    result = is_queue_dirty(git_common_dir)

    assert result is True


def test_clear_queue_dirty_removes_marker(tmp_path: Path) -> None:
    """Test that clear_queue_dirty removes the marker file."""
    git_common_dir = str(tmp_path)

    mark_queue_dirty(git_common_dir)
    assert is_queue_dirty(git_common_dir)

    clear_queue_dirty(git_common_dir)

    assert not is_queue_dirty(git_common_dir)


def test_mark_queue_dirty_creates_parent_dir(tmp_path: Path) -> None:
    """Test that mark_queue_dirty creates parent directory if needed."""
    git_common_dir = str(tmp_path)

    # Parent directory shouldn't exist yet
    parent_dir = tmp_path / "vibe3"
    assert not parent_dir.exists()

    mark_queue_dirty(git_common_dir)

    # Parent directory should now exist
    assert parent_dir.exists()
    assert parent_dir.is_dir()


def test_clear_queue_dirty_noop_when_absent(tmp_path: Path) -> None:
    """Test that clear_queue_dirty is a no-op when marker doesn't exist."""
    git_common_dir = str(tmp_path)

    # Should not raise even if marker doesn't exist
    clear_queue_dirty(git_common_dir)

    assert not is_queue_dirty(git_common_dir)
