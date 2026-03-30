"""Tests for shared change-scope utilities."""

from vibe3.services.change_scope_service import (
    classify_changed_files,
    count_changed_lines,
    is_test_file,
)


def test_is_test_file_recognizes_common_patterns() -> None:
    assert is_test_file("tests/vibe3/services/test_check_service.py")
    assert is_test_file("src/vibe3/foo/tests/bar.py")
    assert is_test_file("foo_test.py")
    assert not is_test_file("src/vibe3/services/check_service.py")


def test_classify_changed_files_splits_existing_and_deleted(tmp_path) -> None:
    src = tmp_path / "src/vibe3/services"
    tests = tmp_path / "tests/vibe3/services"
    hooks = tmp_path / "scripts/hooks"
    src.mkdir(parents=True)
    tests.mkdir(parents=True)
    hooks.mkdir(parents=True)

    (src / "foo.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (tests / "test_foo.py").write_text(
        "def test_foo():\n    assert True\n", encoding="utf-8"
    )
    (hooks / "pre-push.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    scope = classify_changed_files(
        [
            "src/vibe3/services/foo.py",
            "tests/vibe3/services/test_foo.py",
            "scripts/hooks/pre-push.sh",
            "src/vibe3/services/missing.py",
            "docs/README.md",
        ],
        repo_root=tmp_path,
    )

    assert "src/vibe3/services/foo.py" in scope.existing_files
    assert "src/vibe3/services/missing.py" in scope.deleted_files
    assert "tests/vibe3/services/test_foo.py" in scope.v3_test_files
    assert "src/vibe3/services/foo.py" in scope.v3_source_files
    assert "scripts/hooks/pre-push.sh" in scope.hook_files
    assert "docs/README.md" in scope.other_files


def test_count_changed_lines_supports_optional_path_filter() -> None:
    diff_text = "\n".join(
        [
            "diff --git a/src/vibe3/services/foo.py b/src/vibe3/services/foo.py",
            "--- a/src/vibe3/services/foo.py",
            "+++ b/src/vibe3/services/foo.py",
            "+new_line",
            "-old_line",
            "diff --git a/docs/README.md b/docs/README.md",
            "--- a/docs/README.md",
            "+++ b/docs/README.md",
            "+doc_line",
        ]
    )

    assert count_changed_lines(diff_text) == 3
    assert count_changed_lines(diff_text, code_paths=["src/"]) == 2
