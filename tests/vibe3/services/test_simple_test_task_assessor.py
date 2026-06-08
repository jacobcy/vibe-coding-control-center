"""Unit tests for simple_test_task_assessor service."""

from __future__ import annotations

from vibe3.services.simple_test_task_assessor import (
    MAX_FILES,
    MAX_LINES,
    is_simple_test_from_diff,
    is_simple_test_task_from_metadata,
)


class TestIsSimpleTestTaskFromMetadata:
    """Tests for is_simple_test_task_from_metadata function."""

    def test_title_with_test_keyword(self) -> None:
        """Title with test keyword should return True."""
        assert is_simple_test_task_from_metadata("fix flaky test_something", []) is True

    def test_title_without_test_keyword(self) -> None:
        """Title without test keyword should return False."""
        assert is_simple_test_task_from_metadata("add new feature X", []) is False

    def test_title_with_complex_label(self) -> None:
        """Title with complex label should return False."""
        assert (
            is_simple_test_task_from_metadata(
                "improve test coverage for Y", ["roadmap/epic"]
            )
            is False
        )

    def test_title_with_chinese_keyword(self) -> None:
        """Title with Chinese test keyword should return True."""
        assert is_simple_test_task_from_metadata("修复测试", []) is True

    def test_empty_title(self) -> None:
        """Empty title should return False."""
        assert is_simple_test_task_from_metadata("", []) is False

    def test_title_with_coverage_keyword(self) -> None:
        """Title with coverage keyword should return True."""
        assert (
            is_simple_test_task_from_metadata("add coverage for module X", []) is True
        )

    def test_title_with_priority_0_label(self) -> None:
        """Title with priority/0 label should return False."""
        assert (
            is_simple_test_task_from_metadata("fix test failure", ["priority/0"])
            is False
        )

    def test_title_with_priority_1_label(self) -> None:
        """Title with priority/1 label should return False."""
        assert (
            is_simple_test_task_from_metadata("fix test failure", ["priority/1"])
            is False
        )

    def test_title_with_multiple_labels(self) -> None:
        """Title with multiple labels, none complex, should return True."""
        assert (
            is_simple_test_task_from_metadata(
                "fix flaky test", ["bug", "component/test"]
            )
            is True
        )

    def test_title_with_flaky_keyword(self) -> None:
        """Title with flaky keyword should return True."""
        assert is_simple_test_task_from_metadata("flaky test needs fixing", []) is True


class TestIsSimpleTestFromDiff:
    """Tests for is_simple_test_from_diff function."""

    def test_small_test_change(self) -> None:
        """Small test change should return True."""
        files = ["tests/test_one.py", "tests/test_two.py", "tests/test_three.py"]
        assert is_simple_test_from_diff(files, 30, 20) is True

    def test_exceeds_max_files(self) -> None:
        """Change exceeding MAX_FILES should return False."""
        files = [f"tests/test_{i}.py" for i in range(MAX_FILES + 1)]
        assert is_simple_test_from_diff(files, 10, 10) is False

    def test_exceeds_max_lines(self) -> None:
        """Change exceeding MAX_LINES should return False."""
        files = ["tests/test_one.py", "tests/test_two.py"]
        assert is_simple_test_from_diff(files, 80, 30) is False

    def test_mixed_files(self) -> None:
        """Mixed test and source files should return False."""
        files = ["tests/test_one.py", "tests/test_two.py", "src/module.py"]
        assert is_simple_test_from_diff(files, 10, 10) is False

    def test_conftest_only(self) -> None:
        """Conftest.py only should return True."""
        files = ["tests/conftest.py"]
        assert is_simple_test_from_diff(files, 10, 5) is True

    def test_empty_file_list(self) -> None:
        """Empty file list should return False."""
        assert is_simple_test_from_diff([], 0, 0) is False

    def test_test_underscore_pattern(self) -> None:
        """Files with test_ prefix should be recognized."""
        files = ["tests/test_module.py"]
        assert is_simple_test_from_diff(files, 10, 10) is True

    def test_test_suffix_pattern(self) -> None:
        """Files with _test.py suffix should be recognized."""
        files = ["tests/module_test.py"]
        assert is_simple_test_from_diff(files, 10, 10) is True

    def test_exactly_max_files(self) -> None:
        """Exactly MAX_FILES should return True."""
        files = [f"tests/test_{i}.py" for i in range(MAX_FILES)]
        assert is_simple_test_from_diff(files, 10, 10) is True

    def test_exactly_max_lines(self) -> None:
        """Exactly MAX_LINES should return True."""
        files = ["tests/test_one.py"]
        total_lines = MAX_LINES
        assert is_simple_test_from_diff(files, total_lines, 0) is True

    def test_large_diff_in_test_files(self) -> None:
        """Large diff even in test files should return False."""
        files = ["tests/test_one.py"]
        assert is_simple_test_from_diff(files, 100, 100) is False

    def test_non_test_file_pattern(self) -> None:
        """Non-test files should return False."""
        files = ["src/module.py", "docs/readme.md"]
        assert is_simple_test_from_diff(files, 10, 10) is False

    def test_pytest_keyword_in_title(self) -> None:
        """Title with pytest keyword should return True."""
        assert (
            is_simple_test_task_from_metadata("update pytest configuration", []) is True
        )

    def test_mock_keyword_in_title(self) -> None:
        """Title with mock keyword should return True."""
        assert (
            is_simple_test_task_from_metadata("add mock for external API", []) is True
        )

    def test_fixture_keyword_in_title(self) -> None:
        """Title with fixture keyword should return True."""
        assert (
            is_simple_test_task_from_metadata("create fixture for database", []) is True
        )
