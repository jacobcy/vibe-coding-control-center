"""Tests for _get_commit_files helper function.

Tests internal helper used by git_status_ops.
All external services are mocked.
"""

from vibe3.clients.git_status_ops import _get_commit_files


def test__get_commit_files_merge_commit_with_duplicates():
    def mock_run(cmd):
        return """file1.py
file2.py
file1.py
file3.py
file2.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
    assert len(result) == 3


def test__get_commit_files_regular_commit_no_duplicates():
    def mock_run(cmd):
        return """file1.py
file2.py
file3.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
    assert len(result) == 3


def test__get_commit_files_empty_output():
    def mock_run(cmd):
        return ""

    result = _get_commit_files(mock_run, "abc123")
    assert result == []


def test__get_commit_files_whitespace_only_lines():
    def mock_run(cmd):
        return """file1.py

file2.py

file3.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
