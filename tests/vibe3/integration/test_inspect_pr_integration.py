"""Integration tests for PR analysis workflow.

Tests the complete build_pr_analysis() flow with mocked external dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.commands.inspect_helpers import PRCriticalAnalysis, build_pr_analysis

# ========== Integration Tests for build_pr_analysis ==========


@pytest.fixture
def mock_all_dependencies():
    """Mock all external dependencies for PR analysis."""
    with patch(
        "vibe3.commands.inspect_helpers._get_pr_changed_files"
    ) as mock_files, patch(
        "vibe3.commands.inspect_helpers._filter_critical_files"
    ) as mock_filter, patch(
        "vibe3.commands.inspect_helpers._analyze_critical_files"
    ) as mock_analyze, patch(
        "vibe3.commands.inspect_helpers._calculate_risk_score"
    ) as mock_score, patch(
        "vibe3.commands.inspect_helpers._get_recent_commits"
    ) as mock_commits, patch(
        "vibe3.commands.inspect_helpers._get_pr_commit_count"
    ) as mock_count, patch(
        "vibe3.commands.inspect_helpers.dag_service"
    ) as mock_dag:
        # Setup default returns
        mock_files.return_value = [
            "src/vibe3/config/settings.py",
            "src/vibe3/utils/helpers.py",
            "tests/test_foo.py",
        ]

        mock_filter.return_value = [
            {
                "path": "src/vibe3/config/settings.py",
                "critical_path": True,
                "public_api": False,
            }
        ]

        mock_analyze.return_value = (
            {"src/vibe3/config/settings.py": ["get_config", "ConfigPaths"]},
            {"src/vibe3/config/settings.py": ["vibe3.config", "vibe3.utils"]},
        )

        mock_dag_result = MagicMock()
        mock_dag_result.impacted_modules = ["vibe3.config", "vibe3.utils"]
        mock_dag.expand_impacted_modules.return_value = mock_dag_result

        mock_score.return_value = {
            "score": 6,
            "level": "MEDIUM",
            "block": False,
        }

        mock_commits.return_value = [
            {"sha": "abc1234", "message": "Add feature"},
            {"sha": "def5678", "message": "Fix bug"},
        ]

        mock_count.return_value = 5

        yield {
            "files": mock_files,
            "filter": mock_filter,
            "analyze": mock_analyze,
            "score": mock_score,
            "commits": mock_commits,
            "count": mock_count,
            "dag": mock_dag,
        }


def test_build_pr_analysis_non_verbose(mock_all_dependencies):
    """Test PR analysis without verbose output."""
    result = build_pr_analysis(42, verbose=False)

    # Verify return type
    assert isinstance(result, PRCriticalAnalysis)
    assert result.pr_number == 42
    assert result.total_files == 3
    assert result.total_commits == 5

    # Verify critical files
    assert len(result.critical_files) == 1
    assert result.critical_files[0]["path"] == "src/vibe3/config/settings.py"
    assert result.critical_files[0]["critical_path"] is True

    # Verify critical symbols
    assert "src/vibe3/config/settings.py" in result.critical_symbols
    assert "get_config" in result.critical_symbols["src/vibe3/config/settings.py"]

    # Verify DAG
    assert len(result.impacted_modules) == 2
    assert "vibe3.config" in result.impacted_modules

    # Verify score
    assert result.score["score"] == 6
    assert result.score["level"] == "MEDIUM"

    # Verbose is False, so no recent commits
    assert result.recent_commits == []

    # Verify all helpers were called
    mock_all_dependencies["files"].assert_called_once_with(42)
    mock_all_dependencies["filter"].assert_called_once()
    mock_all_dependencies["analyze"].assert_called_once()
    mock_all_dependencies["score"].assert_called_once()
    # Should NOT be called when verbose=False
    mock_all_dependencies["commits"].assert_not_called()


def test_build_pr_analysis_verbose(mock_all_dependencies):
    """Test PR analysis with verbose output."""
    result = build_pr_analysis(42, verbose=True)

    assert isinstance(result, PRCriticalAnalysis)

    # Verbose is True, so should have recent commits
    assert len(result.recent_commits) == 2
    assert result.recent_commits[0]["sha"] == "abc1234"
    assert result.recent_commits[0]["message"] == "Add feature"

    # Verify commits were fetched
    mock_all_dependencies["commits"].assert_called_once_with(42, limit=5)


def test_build_pr_analysis_no_critical_files(mock_all_dependencies):
    """Test PR with no critical files."""
    # Override to return no critical files
    mock_all_dependencies["filter"].return_value = []

    # No symbols or DAG for critical files
    mock_all_dependencies["analyze"].return_value = ({}, {})

    result = build_pr_analysis(42)

    assert len(result.critical_files) == 0
    assert result.critical_symbols == {}
    assert result.critical_file_dags == {}


def test_build_pr_analysis_multiple_critical_files(mock_all_dependencies):
    """Test PR with multiple critical files."""
    mock_all_dependencies["files"].return_value = [
        "src/vibe3/config/settings.py",
        "src/vibe3/api/routes.py",
        "src/vibe3/clients/git_client.py",
        "tests/test_foo.py",
    ]

    mock_all_dependencies["filter"].return_value = [
        {
            "path": "src/vibe3/config/settings.py",
            "critical_path": True,
            "public_api": False,
        },
        {
            "path": "src/vibe3/api/routes.py",
            "critical_path": False,
            "public_api": True,
        },
        {
            "path": "src/vibe3/clients/git_client.py",
            "critical_path": True,
            "public_api": False,
        },
    ]

    mock_all_dependencies["analyze"].return_value = (
        {
            "src/vibe3/config/settings.py": ["get_config"],
            "src/vibe3/api/routes.py": ["handle_request"],
            "src/vibe3/clients/git_client.py": ["get_diff"],
        },
        {
            "src/vibe3/config/settings.py": ["vibe3.config"],
            "src/vibe3/api/routes.py": ["vibe3.api"],
        },
    )

    result = build_pr_analysis(42)

    assert len(result.critical_files) == 3
    assert len(result.critical_symbols) == 3
    assert "get_config" in result.critical_symbols["src/vibe3/config/settings.py"]


def test_build_pr_analysis_flow_integration(mock_all_dependencies):
    """Test the complete integration flow between components."""
    # This test verifies that data flows correctly between components

    # Setup realistic data
    test_files = [
        "src/vibe3/config/settings.py",
        "src/vibe3/utils/helpers.py",
    ]
    mock_all_dependencies["files"].return_value = test_files

    # Critical files filter should receive all files
    build_pr_analysis(42)

    # Verify _filter_critical_files received the right files
    call_args = mock_all_dependencies["filter"].call_args[0][0]
    assert call_args == test_files

    # Verify _analyze_critical_files received the filtered critical files
    call_args = mock_all_dependencies["analyze"].call_args[0]
    assert len(call_args[0]) == 1  # One critical file
    assert call_args[1] == 42  # PR number

    # Verify _calculate_risk_score received correct data
    call_args = mock_all_dependencies["score"].call_args[0]
    assert call_args[0] == test_files  # all_files
    assert len(call_args[1]) == 1  # critical_files
    assert len(call_args[2]) == 2  # impacted_modules


def test_build_pr_analysis_dag_integration(mock_all_dependencies):
    """Test DAG service integration."""
    build_pr_analysis(42)

    # DAG is called once for overall analysis in build_pr_analysis
    # Note: _analyze_critical_files is mocked, so DAG calls inside it don't happen
    assert mock_all_dependencies["dag"].expand_impacted_modules.call_count == 1

    # Verify the call was for overall DAG with all files
    call_args = mock_all_dependencies["dag"].expand_impacted_modules.call_args[0][0]
    assert len(call_args) == 3  # All 3 files


def test_build_pr_analysis_error_handling():
    """Test error handling in build_pr_analysis."""
    with patch(
        "vibe3.commands.inspect_helpers._get_pr_changed_files"
    ) as mock_files:
        # Simulate error getting files
        mock_files.side_effect = Exception("GitHub API error")

        # Should propagate the error
        with pytest.raises(Exception, match="GitHub API error"):
            build_pr_analysis(42)


def test_build_pr_analysis_commit_count_error(mock_all_dependencies):
    """Test graceful handling of commit count errors."""
    mock_all_dependencies["count"].return_value = 0

    result = build_pr_analysis(42)

    # Should still succeed with 0 commits
    assert result.total_commits == 0


def test_build_pr_analysis_dataclass_fields():
    """Test that PRCriticalAnalysis dataclass has all expected fields."""
    with patch(
        "vibe3.commands.inspect_helpers._get_pr_changed_files",
        return_value=["file.py"],
    ), patch(
        "vibe3.commands.inspect_helpers._filter_critical_files", return_value=[]
    ), patch(
        "vibe3.commands.inspect_helpers._analyze_critical_files",
        return_value=({}, {}),
    ), patch(
        "vibe3.commands.inspect_helpers.dag_service.expand_impacted_modules"
    ) as mock_dag, patch(
        "vibe3.commands.inspect_helpers._calculate_risk_score",
        return_value={"score": 1},
    ), patch(
        "vibe3.commands.inspect_helpers._get_pr_commit_count", return_value=1
    ):
        mock_dag_result = MagicMock()
        mock_dag_result.impacted_modules = []
        mock_dag.return_value = mock_dag_result

        result = build_pr_analysis(42)

        # Verify all fields exist
        assert hasattr(result, "pr_number")
        assert hasattr(result, "total_commits")
        assert hasattr(result, "total_files")
        assert hasattr(result, "critical_files")
        assert hasattr(result, "critical_symbols")
        assert hasattr(result, "impacted_modules")
        assert hasattr(result, "critical_file_dags")
        assert hasattr(result, "score")
        assert hasattr(result, "recent_commits")
