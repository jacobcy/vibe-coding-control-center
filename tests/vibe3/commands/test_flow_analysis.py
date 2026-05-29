"""Tests for flow analysis commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app as flow_app

runner = CliRunner()


# ==============================================================================
# sync-status tests
# ==============================================================================


@patch("vibe3.commands.flow_analysis.GitClient")
def test_sync_status_clean(mock_git_client_cls) -> None:
    """sync-status with behind=0, ahead=0, no conflicts."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "0",  # behind count
        "0",  # ahead count
    ]

    result = runner.invoke(flow_app, ["sync-status"])

    assert result.exit_code == 0
    mock_client.fetch.assert_called_once_with(remote="origin", ref="main")


@patch("vibe3.commands.flow_analysis.GitClient")
def test_sync_status_behind(mock_git_client_cls) -> None:
    """sync-status with behind>0 should list new commits."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "3",  # behind count
        "0",  # ahead count
        # sha + subjects
        "abc1234 fix: login\ndef5678 feat: rate limit\nghi9012 docs: API",
    ]

    result = runner.invoke(flow_app, ["sync-status"])

    assert result.exit_code == 0
    assert "abc1234" in result.stdout


@patch("vibe3.commands.flow_analysis.GitClient")
def test_sync_status_ahead(mock_git_client_cls) -> None:
    """sync-status with ahead>0."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "0",  # behind count
        "2",  # ahead count
    ]

    result = runner.invoke(flow_app, ["sync-status"])

    assert result.exit_code == 0
    assert "Ahead:  2 commits" in result.stdout


@patch("vibe3.commands.flow_analysis.GitClient")
def test_sync_status_conflict(mock_git_client_cls) -> None:
    """sync-status with --check-conflicts detecting conflict."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "1",  # behind count
        "0",  # ahead count
        "fix: something",  # subjects
        "abc1234 fix: something",  # sha + subjects
    ]
    mock_client.check_merge_conflicts.return_value = True

    result = runner.invoke(flow_app, ["sync-status", "--check-conflicts"])

    assert result.exit_code == 0
    mock_client.check_merge_conflicts.assert_called_once_with("origin/main")


@patch("vibe3.commands.flow_analysis.GitClient")
def test_sync_status_json(mock_git_client_cls) -> None:
    """sync-status --format json output."""
    import json

    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "1",  # behind count
        "0",  # ahead count
        "abc1234 fix: bug",  # sha + subjects
    ]

    result = runner.invoke(flow_app, ["sync-status", "--format", "json"])

    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["behind"] == 1
    assert output["ahead"] == 0
    assert output["conflict"] is False
    assert len(output["new_commits"]) == 1


@patch("vibe3.commands.flow_analysis.GitClient")
def test_sync_status_custom_target(mock_git_client_cls) -> None:
    """sync-status --target dev."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "0",  # behind count
        "0",  # ahead count
    ]

    result = runner.invoke(flow_app, ["sync-status", "--target", "dev"])

    assert result.exit_code == 0
    mock_client.fetch.assert_called_once_with(remote="origin", ref="dev")


# ==============================================================================
# changes tests
# ==============================================================================


@patch("vibe3.commands.flow_analysis.GitClient")
def test_changes_clean(mock_git_client_cls) -> None:
    """changes with no modifications."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "",  # status porcelain
        "",  # staged stat (no staged files)
        "",  # unstaged stat (no unstaged files)
    ]

    result = runner.invoke(flow_app, ["changes"])

    assert result.exit_code == 0


@patch("vibe3.commands.flow_analysis.GitClient")
def test_changes_staged_only(mock_git_client_cls) -> None:
    """changes with staged files only."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "M  src/main.py\nM  tests/test_main.py",  # status porcelain (staged = 'M ')
        "src/main.py | 5 ++++-",  # staged stat
        "",  # unstaged stat
    ]

    result = runner.invoke(flow_app, ["changes"])

    assert result.exit_code == 0
    assert "Staged (2 files)" in result.stdout


@patch("vibe3.commands.flow_analysis.GitClient")
def test_changes_unstaged_only(mock_git_client_cls) -> None:
    """changes with unstaged files only."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        " M src/utils.py",  # status porcelain (unstaged = ' M')
        "",  # staged stat
        "src/utils.py | 3 ++-",  # unstaged stat
    ]

    result = runner.invoke(flow_app, ["changes"])

    assert result.exit_code == 0
    assert "Unstaged (1 file)" in result.stdout


@patch("vibe3.commands.flow_analysis.GitClient")
def test_changes_mixed(mock_git_client_cls) -> None:
    """changes with staged + unstaged + untracked."""
    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "M  src/main.py\n M src/utils.py\n?? new_file.py",  # status porcelain
        "src/main.py | 5 ++++-",  # staged stat
        "src/utils.py | 3 ++-",  # unstaged stat
    ]

    result = runner.invoke(flow_app, ["changes"])

    assert result.exit_code == 0
    assert "Staged (1 file)" in result.stdout
    assert "Unstaged (1 file)" in result.stdout
    assert "Untracked (1 file)" in result.stdout


@patch("pathlib.Path.cwd")
@patch("vibe3.commands.flow_analysis.GitClient")
def test_changes_debug_files(mock_git_client_cls, mock_cwd) -> None:
    """changes detecting debug files."""
    from pathlib import Path
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "",  # status porcelain
        "",  # staged stat
        "",  # unstaged stat
    ]

    # Mock cwd() and glob results
    mock_file1 = MagicMock(spec=Path)
    mock_file1.name = "debug_test.py"
    mock_file2 = MagicMock(spec=Path)
    mock_file2.name = "tmp_cache.py"

    mock_cwd.return_value.glob.side_effect = [
        [mock_file1],  # debug_*.py
        [],  # debug_*.sh
        [mock_file2],  # tmp_*.py
    ]

    result = runner.invoke(flow_app, ["changes"])

    assert result.exit_code == 0
    assert "Debug files found" in result.stdout
    assert "debug_test.py" in result.stdout


@patch("vibe3.commands.flow_analysis.GitClient")
def test_changes_json(mock_git_client_cls) -> None:
    """changes --format json output."""
    import json

    mock_client = MagicMock()
    mock_git_client_cls.return_value = mock_client

    # Mock responses
    mock_client._run.side_effect = [
        "M  src/main.py",  # status porcelain
        "src/main.py | 5 ++++-",  # staged stat
        "",  # unstaged stat
    ]

    result = runner.invoke(flow_app, ["changes", "--format", "json"])

    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert len(output["staged"]) == 1
    assert len(output["unstaged"]) == 0
    assert len(output["untracked"]) == 0
    assert isinstance(output["debug_files"], list)
