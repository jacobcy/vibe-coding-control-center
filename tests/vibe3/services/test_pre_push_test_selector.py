"""Tests for pre-push incremental test selector."""

from vibe3.services.pre_push_test_selector import select_pre_push_tests


def test_selects_changed_test_files_incrementally() -> None:
    selection = select_pre_push_tests(["tests/vibe3/services/test_pre_push_scope.py"])

    assert selection.mode == "incremental"
    assert selection.tests == ["tests/vibe3/services/test_pre_push_scope.py"]


def test_maps_source_file_to_related_tests() -> None:
    selection = select_pre_push_tests(["src/vibe3/services/pre_push_scope.py"])

    assert selection.mode == "incremental"
    assert "tests/vibe3/services/test_pre_push_scope.py" in selection.tests


def test_falls_back_to_dir_when_source_mapping_missing() -> None:
    # A real source file with no exact test file match should scope to
    # the test directory rather than the full suite.
    selection = select_pre_push_tests(
        ["src/vibe3/services/not_real_selector_target.py"]
    )

    assert selection.mode == "incremental"
    assert selection.tests == ["tests/vibe3/services"]
    assert selection.unmapped_sources == [
        "src/vibe3/services/not_real_selector_target.py"
    ]


def test_falls_back_to_full_when_test_dir_missing() -> None:
    # If the corresponding test directory doesn't exist at all, fall back
    # to the full suite.
    selection = select_pre_push_tests(
        ["src/vibe3/nonexistent_subpackage/some_module.py"]
    )

    assert selection.mode == "full"
    assert selection.tests == ["tests/vibe3"]


def test_uses_smoke_fallback_when_no_targets() -> None:
    selection = select_pre_push_tests(["docs/README.md"])

    assert selection.mode == "smoke"
    assert "tests/vibe3/services/test_pre_push_scope.py" in selection.tests


def test_maps_hook_changes_to_hook_regression_tests() -> None:
    selection = select_pre_push_tests(["scripts/hooks/pre-push.sh"])

    assert selection.mode == "incremental"
    assert "tests/vibe3/integration/test_review_shell_contract.py" in selection.tests
