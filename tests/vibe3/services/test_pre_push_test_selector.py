"""Tests for pre-push incremental test selector."""

from vibe3.analysis.pre_push_test_selector import select_pre_push_tests


def test_selects_changed_test_files_incrementally() -> None:
    selection = select_pre_push_tests(["tests/vibe3/services/test_pre_push_scope.py"])

    assert selection.mode == "incremental"
    assert selection.tests == ["tests/vibe3/services/test_pre_push_scope.py"]


def test_maps_source_file_to_related_tests() -> None:
    selection = select_pre_push_tests(["src/vibe3/services/pre_push_scope.py"])

    assert selection.mode == "incremental"
    assert "tests/vibe3/services/test_pre_push_scope.py" in selection.tests


def test_dag_resolves_tests_for_unmapped_source() -> None:
    # signature_service.py has no test_signature_service.py (name miss).
    # But check_service.py imports it, and test_flow_status.py imports check_service.
    # DAG layer should narrow to those tests instead of the full services directory.
    selection = select_pre_push_tests(["src/vibe3/services/signature_service.py"])

    assert selection.mode == "incremental"
    # Must include tests that import check_service (which imports the mixin)
    assert "tests/vibe3/services/test_flow_status.py" in selection.tests
    # Must NOT fall back to the full directory
    assert "tests/vibe3/services" not in selection.tests
    assert selection.unmapped_sources == ["src/vibe3/services/signature_service.py"]


def test_falls_back_to_dir_when_source_mapping_missing() -> None:
    # A real source file with no exact test file match AND no tests importing it
    # via DAG should scope to the test directory rather than the full suite.
    selection = select_pre_push_tests(
        ["src/vibe3/services/not_real_selector_target.py"]
    )

    assert selection.mode == "incremental"
    assert selection.tests == ["tests/vibe3/services"]
    assert selection.unmapped_sources == [
        "src/vibe3/services/not_real_selector_target.py"
    ]


def test_skips_when_test_dir_missing() -> None:
    # If the corresponding test directory doesn't exist at all, skip local run
    # instead of falling back to full suite (CI covers full suite).
    selection = select_pre_push_tests(
        ["src/vibe3/nonexistent_subpackage/some_module.py"]
    )

    assert selection.mode == "skip"
    assert selection.tests == []


def test_uses_smoke_fallback_when_no_targets() -> None:
    selection = select_pre_push_tests(["docs/README.md"])

    assert selection.mode == "smoke"
    assert "tests/vibe3/services/test_pre_push_scope.py" in selection.tests


def test_skips_when_no_applicable_files() -> None:
    # Non-Python, non-hook changes should skip (not go to full suite).
    # CI handles full coverage; locally there's nothing deterministic to run.
    selection = select_pre_push_tests(["docs/standards/some-standard.md"])

    assert selection.mode in ("smoke", "skip")
    # Either smoke (if smoke files exist) or skip - both are acceptable;
    # the key invariant is it must NOT fall back to full suite.
    assert selection.tests != ["tests/vibe3"]


def test_maps_hook_changes_to_hook_regression_tests() -> None:
    selection = select_pre_push_tests(["scripts/hooks/pre-push.sh"])

    assert selection.mode == "incremental"
    assert "tests/vibe3/integration/test_review_shell_contract.py" in selection.tests
