"""Unit tests for inspect base helpers."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.commands.inspect_base_helpers import (
    _is_code_file,
    _merge_symbol_map,
    build_json_output,
    count_changed_lines_in_code_paths,
    validate_base_branch,
)
from vibe3.exceptions import GitError, UserError


def test_is_code_file() -> None:
    """Test _is_code_file logic."""
    code_paths = ["src/vibe3/", "lib/"]
    assert _is_code_file("src/vibe3/main.py", code_paths) is True
    assert _is_code_file("lib/utils.py", code_paths) is True
    assert _is_code_file("tests/test_main.py", code_paths) is False
    assert _is_code_file("README.md", code_paths) is False
    # Test path normalization (trailing slash)
    assert _is_code_file("src/vibe3/sub/file.py", ["src/vibe3/"]) is True


def test_merge_symbol_map() -> None:
    """Test merging symbol maps."""
    target = {"file1.py": ["sym1", "sym2"]}
    incoming = {
        "file1.py": ["sym2", "sym3"],
        "file2.py": ["symA"],
    }
    _merge_symbol_map(target, incoming)

    assert target == {
        "file1.py": ["sym1", "sym2", "sym3"],
        "file2.py": ["symA"],
    }


def test_validate_base_branch_exists() -> None:
    """Test validate_base_branch when branch exists."""
    mock_git = MagicMock()
    # Mock _run to succeed for the first call
    mock_git._run.return_value = None

    # Should not raise
    validate_base_branch(mock_git, "main")
    assert mock_git._run.call_count == 1


def test_validate_base_branch_resolved_via_remotes() -> None:
    """Test validate_base_branch when branch is found in remotes."""
    mock_git = MagicMock()

    def side_effect(cmd: list[str]) -> None:
        if "refs/remotes/origin/develop" in cmd:
            return None
        raise GitError("rev-parse", "Not found")

    mock_git._run.side_effect = side_effect

    # Should not raise
    validate_base_branch(mock_git, "develop")
    assert mock_git._run.call_count >= 1


def test_validate_base_branch_resolved_via_heads() -> None:
    """Test validate_base_branch when branch found in refs/heads."""
    mock_git = MagicMock()

    def side_effect(cmd: list[str]) -> None:
        if "refs/heads/develop" in cmd:
            return None
        raise GitError("rev-parse", "Not found")

    mock_git._run.side_effect = side_effect

    # Should not raise
    validate_base_branch(mock_git, "develop")
    assert mock_git._run.call_count >= 1


def test_validate_base_branch_resolved_via_remotes_no_origin() -> None:
    """Test validate_base_branch when branch found in refs/remotes (not origin)."""
    mock_git = MagicMock()

    def side_effect(cmd: list[str]) -> None:
        if "refs/remotes/upstream/main" in cmd:
            return None
        raise GitError("rev-parse", "Not found")

    mock_git._run.side_effect = side_effect

    # Should not raise
    validate_base_branch(mock_git, "upstream/main")
    assert mock_git._run.call_count >= 1


def test_validate_base_branch_not_found() -> None:
    """Test validate_base_branch raises UserError if branch not found."""
    mock_git = MagicMock()
    mock_git._run.side_effect = GitError("rev-parse", "Not found")

    with pytest.raises(UserError) as exc:
        validate_base_branch(mock_git, "invalid-branch")

    assert "Base branch 'invalid-branch' not found" in str(exc.value)


@patch("vibe3.commands.inspect_base_helpers.get_config")
@patch("vibe3.commands.inspect_base_helpers.count_changed_lines")
def test_count_changed_lines_in_code_paths(
    mock_count: MagicMock, mock_get_config: MagicMock
) -> None:
    """Test count_changed_lines_in_code_paths."""
    mock_git = MagicMock()
    mock_git.get_diff.return_value = "diff content"
    mock_get_config.return_value.code_limits.code_paths.v2_shell = ["lib/"]
    mock_get_config.return_value.code_limits.code_paths.v3_python = ["src/vibe3/"]
    mock_count.return_value = 42

    source = MagicMock()
    result = count_changed_lines_in_code_paths(mock_git, source)

    mock_git.get_diff.assert_called_once_with(source, pathspec=["lib/", "src/vibe3/"])
    mock_count.assert_called_once_with("diff content")
    assert result == 42


@patch("vibe3.commands.inspect_base_helpers.get_config")
@patch("vibe3.commands.inspect_base_helpers.SerenaService")
@patch("vibe3.commands.inspect_base_helpers.collect_changed_symbols")
@patch("vibe3.commands.inspect_base_helpers.dag_service")
@patch("vibe3.commands.inspect_base_helpers.generate_score_report")
def test_build_json_output(
    mock_score: MagicMock,
    mock_dag: MagicMock,
    mock_collect: MagicMock,
    mock_serena: MagicMock,
    mock_get_config: MagicMock,
) -> None:
    """Test build_json_output assembly logic."""
    mock_git = MagicMock()
    mock_get_config.return_value.code_limits.code_paths.v2_shell = ["lib/"]
    mock_get_config.return_value.code_limits.code_paths.v3_python = ["src/vibe3/"]

    mock_collect.return_value = ({"src/vibe3/file1.py": ["sym1"]}, 0)
    mock_dag.expand_impacted_modules.return_value.impacted_modules = ["mod1"]
    mock_score.return_value = {"score": 1.0}

    core_files = [
        {"path": "src/vibe3/core.py", "critical_path": True, "public_api": False}
    ]

    result = build_json_output(
        git=mock_git,
        source=MagicMock(),
        current_branch="feat",
        base_branch="main",
        all_changed_files=["src/vibe3/core.py", "README.md"],
        existing_files=["src/vibe3/core.py"],
        deleted_files=[],
        core_files=core_files,
        changed_lines=10,
    )

    assert result["current_branch"] == "feat"
    assert result["base_branch"] == "main"
    assert result["code_changed"] == 1  # Only core.py is in src/vibe3/
    assert result["score"] == {"score": 1.0}
    assert "impacted_modules" in result
    assert result["changed_symbols"] == {"src/vibe3/file1.py": ["sym1"]}


@patch("vibe3.commands.inspect_base_helpers.get_config")
@patch("vibe3.commands.inspect_base_helpers.SerenaService")
@patch("vibe3.commands.inspect_base_helpers.collect_changed_symbols")
@patch("vibe3.commands.inspect_base_helpers.dag_service")
@patch("vibe3.commands.inspect_base_helpers.generate_score_report")
def test_build_json_output_empty_core_files(
    mock_score: MagicMock,
    mock_dag: MagicMock,
    mock_collect: MagicMock,
    mock_serena: MagicMock,
    mock_get_config: MagicMock,
) -> None:
    """Test build_json_output with empty core_files (no impacted_modules)."""
    mock_git = MagicMock()
    mock_get_config.return_value.code_limits.code_paths.v2_shell = ["lib/"]
    mock_get_config.return_value.code_limits.code_paths.v3_python = ["src/vibe3/"]

    mock_collect.return_value = ({}, 0)
    mock_score.return_value = {"score": 0.5}

    result = build_json_output(
        git=mock_git,
        source=MagicMock(),
        current_branch="feat",
        base_branch="main",
        all_changed_files=["README.md"],
        existing_files=["README.md"],
        deleted_files=[],
        core_files=[],
        changed_lines=5,
    )

    assert result["current_branch"] == "feat"
    assert result["code_changed"] == 0  # No code files
    assert "impacted_modules" not in result  # No core files
    assert "changed_symbols" not in result  # No symbols


@patch("vibe3.commands.inspect_base_helpers.get_config")
@patch("vibe3.commands.inspect_base_helpers.SerenaService")
@patch("vibe3.commands.inspect_base_helpers.collect_changed_symbols")
@patch("vibe3.commands.inspect_base_helpers.dag_service")
@patch("vibe3.commands.inspect_base_helpers.generate_score_report")
def test_build_json_output_with_source_file_sets(
    mock_score: MagicMock,
    mock_dag: MagicMock,
    mock_collect: MagicMock,
    mock_serena: MagicMock,
    mock_get_config: MagicMock,
) -> None:
    """Test build_json_output with source_file_sets parameter."""
    mock_git = MagicMock()
    mock_get_config.return_value.code_limits.code_paths.v2_shell = ["lib/"]
    mock_get_config.return_value.code_limits.code_paths.v3_python = ["src/vibe3/"]

    # Mock different results for different sources
    mock_collect.side_effect = [
        ({"src/file1.py": ["sym1"]}, 0),
        ({"src/file2.py": ["sym2"]}, 1),
    ]
    mock_dag.expand_impacted_modules.return_value.impacted_modules = ["mod1"]
    mock_score.return_value = {"score": 1.0}

    source1 = MagicMock()
    source2 = MagicMock()
    result = build_json_output(
        git=mock_git,
        source=source1,
        current_branch="feat",
        base_branch="main",
        all_changed_files=["src/file1.py", "src/file2.py"],
        existing_files=["src/file1.py", "src/file2.py"],
        deleted_files=[],
        core_files=[],
        changed_lines=10,
        source_file_sets=[(source1, ["src/file1.py"]), (source2, ["src/file2.py"])],
    )

    assert result["changed_symbols"] == {
        "src/file1.py": ["sym1"],
        "src/file2.py": ["sym2"],
    }
    assert mock_collect.call_count == 2


@patch("typer.echo")
def test_print_human_output(mock_echo: MagicMock) -> None:
    """Test print_human_output handles various cases without crashing."""
    from vibe3.commands.inspect_base_helpers import print_human_output

    core_files = [
        {"path": "src/vibe3/core.py", "critical_path": True, "public_api": False},
        {"path": "src/vibe3/api.py", "critical_path": False, "public_api": True},
    ]

    print_human_output(
        current_branch="feat",
        base_branch="main",
        all_changed_files=["src/vibe3/core.py", "src/vibe3/api.py", "README.md"],
        existing_files=["src/vibe3/core.py", "src/vibe3/api.py"],
        deleted_files=["old.py"],
        core_files=core_files,
    )

    # Verify key elements were printed
    calls = []
    for call in mock_echo.call_args_list:
        if call.args:
            calls.append(call.args[0])
        elif "message" in call.kwargs:
            calls.append(call.kwargs["message"])
        else:
            calls.append("")
    output = "\n".join(calls)

    assert "Branch Analysis: feat vs main" in output
    assert "Deleted files: 1" in output
    assert "Core files changed (2)" in output
    assert "src/vibe3/core.py (critical)" in output
    assert "src/vibe3/api.py (public-api)" in output
    assert "1 critical file(s) changed" in output
