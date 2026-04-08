"""Tests for dead code detection rules."""

from vibe3.analysis.dead_code_rules import (
    classify_confidence,
    is_dead_code,
    is_private,
    should_exclude,
)


class TestShouldExclude:
    """Test exclusion patterns."""

    def test_test_functions(self):
        """Test functions should be excluded."""
        assert should_exclude("test_something") is True
        assert should_exclude("test_") is True

    def test_setup_teardown(self):
        """Setup/teardown functions should be excluded."""
        assert should_exclude("setup") is True
        assert should_exclude("teardown") is True
        assert should_exclude("setup_module") is True
        assert should_exclude("teardown_class") is True

    def test_magic_methods(self):
        """Magic methods should be excluded."""
        assert should_exclude("__init__") is True
        assert should_exclude("__str__") is True
        assert should_exclude("__repr__") is True

    def test_normal_functions(self):
        """Normal functions should NOT be excluded."""
        assert should_exclude("process_data") is False
        assert should_exclude("calculate_total") is False


class TestIsPrivate:
    """Test private function detection."""

    def test_private_functions(self):
        """Functions starting with _ are private."""
        assert is_private("_helper") is True
        assert is_private("__private") is True

    def test_public_functions(self):
        """Public functions don't start with _."""
        assert is_private("public") is False
        assert is_private("test_something") is False


class TestClassifyConfidence:
    """Test confidence classification."""

    def test_cli_commands_excluded(self):
        """CLI commands should be excluded."""
        result = classify_confidence("some_command", ref_count=0, is_cli_command=True)
        assert result == "excluded"

    def test_test_functions_excluded(self):
        """Test functions should be excluded."""
        result = classify_confidence("test_something", ref_count=0)
        assert result == "excluded"

    def test_normal_function_zero_refs_high_confidence(self):
        """Normal function with 0 refs → high confidence."""
        result = classify_confidence("unused_func", ref_count=0)
        assert result == "high"

    def test_private_function_zero_refs_medium_confidence(self):
        """Private function with 0 refs → medium confidence."""
        result = classify_confidence("_private_unused", ref_count=0)
        assert result == "medium"

    def test_function_with_refs_excluded(self):
        """Function with references should be excluded."""
        result = classify_confidence("used_func", ref_count=1)
        assert result == "excluded"


class TestIsDeadCode:
    """Test dead code detection."""

    def test_cli_command_not_dead(self):
        """CLI commands should not be flagged as dead."""
        is_dead, reason = is_dead_code("some_command", ref_count=0, is_cli_command=True)
        assert is_dead is False
        assert "CLI command" in reason

    def test_test_function_not_dead(self):
        """Test functions should not be flagged as dead."""
        is_dead, reason = is_dead_code("test_something", ref_count=0)
        assert is_dead is False
        assert "Excluded pattern" in reason

    def test_normal_function_zero_refs_is_dead(self):
        """Normal function with 0 refs is dead code."""
        is_dead, reason = is_dead_code("unused_func", ref_count=0)
        assert is_dead is True
        assert "high confidence" in reason

    def test_private_function_zero_refs_is_dead(self):
        """Private function with 0 refs is dead code (medium confidence)."""
        is_dead, reason = is_dead_code("_private_unused", ref_count=0)
        assert is_dead is True
        assert "medium confidence" in reason

    def test_function_with_refs_not_dead(self):
        """Function with references is not dead."""
        is_dead, reason = is_dead_code("used_func", ref_count=1)
        assert is_dead is False
        assert "1 references" in reason
