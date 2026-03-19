"""Tests for skipped files handling."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.services.serena_service import SerenaService


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create test files
        (Path(tmp) / "file1.py").write_text("def foo(): pass\n")
        (Path(tmp) / "file2.py").write_text("def bar(): pass\n")
        (Path(tmp) / "file3.py").write_text("def baz(): pass\n")
        yield Path(tmp)


def test_analyze_files_all_exist(temp_dir):
    """Test analyzing files that all exist."""
    # Mock the client and its methods
    mock_client = MagicMock()
    mock_client.get_symbols_overview.return_value = {
        "functions": [{"name": "test_func", "start_line": 1}]
    }
    mock_client.find_references.return_value = {"references": []}

    # Create service
    service = SerenaService(client=mock_client)

    # Test with files that exist
    files = [
        str(temp_dir / "file1.py"),
        str(temp_dir / "file2.py"),
        str(temp_dir / "file3.py"),
    ]
    result = service.analyze_files(files)

    assert len(result["files"]) == 3
    assert "skipped_files" in result
    assert len(result["skipped_files"]) == 0
    assert result["summary"]["skipped_files"] == 0


def test_analyze_files_some_missing(temp_dir):
    """Test analyzing files where some don't exist."""
    # Mock the client
    mock_client = MagicMock()
    mock_client.get_symbols_overview.return_value = {
        "functions": [{"name": "test_func", "start_line": 1}]
    }
    mock_client.find_references.return_value = {"references": []}

    # Create service
    service = SerenaService(client=mock_client)

    # Test with mix of existing and non-existing files
    result = service.analyze_files(
        [
            str(temp_dir / "file1.py"),  # exists
            str(temp_dir / "deleted.py"),  # doesn't exist
            str(temp_dir / "file2.py"),  # exists
        ]
    )

    assert len(result["files"]) == 2
    assert len(result["skipped_files"]) == 1
    assert str(temp_dir / "deleted.py") in result["skipped_files"]
    assert result["summary"]["skipped_files"] == 1


def test_analyze_files_all_missing(temp_dir):
    """Test analyzing files where none exist."""
    # Mock the client
    mock_client = MagicMock()

    # Create service
    service = SerenaService(client=mock_client)

    # Test with all non-existing files
    result = service.analyze_files(
        [
            str(temp_dir / "deleted1.py"),
            str(temp_dir / "deleted2.py"),
        ]
    )

    assert len(result["files"]) == 0
    assert len(result["skipped_files"]) == 2
    assert result["summary"]["skipped_files"] == 2


def test_get_changed_functions_missing_file(temp_dir):
    """Test get_changed_functions with missing file."""
    # Mock git client
    mock_git_client = MagicMock()
    mock_git_client.get_diff_hunk_ranges.return_value = [(1, 10)]

    # Create service
    service = SerenaService(git_client=mock_git_client)

    # Test with non-existing file
    from vibe3.models.change_source import CommitSource

    result = service.get_changed_functions(
        str(temp_dir / "deleted.py"), source=CommitSource(sha="abc123")
    )

    # Should return empty list for missing file
    assert result == []
