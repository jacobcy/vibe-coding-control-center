"""Integration tests for PR analysis workflow.

Tests the complete build_pr_analysis() flow with mocked external dependencies.

Note: Advanced tests (error handling, edge cases, complex scenarios)
are in test_inspect_pr_integration_advanced.py
"""

from vibe3.commands.inspect_helpers import PRCriticalAnalysis, build_pr_analysis

# ========== Integration Tests for build_pr_analysis ==========


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
