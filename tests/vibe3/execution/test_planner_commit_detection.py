"""Tests for planner commit detection in CodeagentExecutionService."""

from unittest.mock import MagicMock, patch

from vibe3.execution.codeagent_runner import CodeagentExecutionService


class TestPlannerCommitDetection:
    """Tests for planner post-execution commit detection."""

    def test_planner_no_commits_passes(self) -> None:
        """Planner execution with no commits passes the check."""
        service = CodeagentExecutionService()
        mock_log = MagicMock()

        # Mock GitClient to return same commit count
        with patch(
            "vibe3.execution.codeagent_runner.GitClient"
        ) as mock_git_client_class:
            mock_git_client = MagicMock()
            mock_git_client.run.return_value = "5"  # Same count before and after
            mock_git_client_class.return_value = mock_git_client

            # Should not raise any exception
            service._check_planner_commits(
                commit_count_before=5,
                branch="task/issue-42",
                actor="claude/sonnet",
                log=mock_log,
            )

        # Should not log any warning
        mock_log.warning.assert_not_called()

    def test_planner_authorized_commits_passes(self) -> None:
        """Planner commits in docs/plans/ and docs/reports/ pass the check."""
        service = CodeagentExecutionService()
        mock_log = MagicMock()

        with patch(
            "vibe3.execution.codeagent_runner.GitClient"
        ) as mock_git_client_class:
            mock_git_client = MagicMock()
            # First call: commit count after (increased)
            # Second call: list of changed files
            mock_git_client._run.side_effect = [
                "6",  # commit_count_after = 6
                "docs/plans/issue-42-plan.md\ndocs/reports/issue-42-report.md",
            ]
            mock_git_client_class.return_value = mock_git_client

            # Should not raise any exception
            service._check_planner_commits(
                commit_count_before=5,
                branch="task/issue-42",
                actor="claude/sonnet",
                log=mock_log,
            )

        # Should log info about new commits and authorized commits
        assert mock_log.info.call_count == 2
        # Last info should mention authorized files
        assert "authorized files" in mock_log.info.call_args_list[-1][0][0]

    def test_planner_unauthorized_commits_flagged(self) -> None:
        """Planner commits outside docs/plans/ trigger finding."""
        service = CodeagentExecutionService()
        mock_log = MagicMock()

        with (
            patch(
                "vibe3.execution.codeagent_runner.GitClient"
            ) as mock_git_client_class,
            patch(
                "vibe3.services.handoff_service.HandoffService"
            ) as mock_handoff_class,
        ):
            mock_git_client = MagicMock()
            # First call: commit count after (increased)
            # Second call: list of changed files (including unauthorized)
            mock_git_client._run.side_effect = [
                "6",  # commit_count_after = 6
                "src/vibe3/execution/codeagent_runner.py\n.agent/policies/plan.md",
            ]
            mock_git_client_class.return_value = mock_git_client

            mock_handoff_instance = MagicMock()
            mock_handoff_class.return_value = mock_handoff_instance

            # Should not raise any exception, but should log and record finding
            service._check_planner_commits(
                commit_count_before=5,
                branch="task/issue-42",
                actor="claude/sonnet",
                log=mock_log,
            )

        # Should log warning about unauthorized files
        assert mock_log.warning.call_count == 1

        # Should record finding to handoff
        mock_handoff_instance.append_current_handoff.assert_called_once()
        call_kwargs = mock_handoff_instance.append_current_handoff.call_args[1]
        assert call_kwargs["branch"] == "task/issue-42"
        assert call_kwargs["kind"] == "finding"
        assert call_kwargs["actor"] == "claude/sonnet"
        assert "unauthorized commit" in call_kwargs["message"].lower()

    def test_planner_mixed_commits_flagged(self) -> None:
        """Planner commits with mixed authorized/unauthorized files trigger finding."""
        service = CodeagentExecutionService()
        mock_log = MagicMock()

        with (
            patch(
                "vibe3.execution.codeagent_runner.GitClient"
            ) as mock_git_client_class,
            patch(
                "vibe3.services.handoff_service.HandoffService"
            ) as mock_handoff_class,
        ):
            mock_git_client = MagicMock()
            # First call: commit count after (increased)
            # Second call: list of changed files (mixed)
            mock_git_client._run.side_effect = [
                "6",  # commit_count_after = 6
                "docs/plans/issue-42-plan.md\nsrc/vibe3/execution/codeagent_runner.py",
            ]
            mock_git_client_class.return_value = mock_git_client

            mock_handoff_instance = MagicMock()
            mock_handoff_class.return_value = mock_handoff_instance

            # Should not raise any exception, but should log and record finding
            service._check_planner_commits(
                commit_count_before=5,
                branch="task/issue-42",
                actor="claude/sonnet",
                log=mock_log,
            )

        # Should log warning about unauthorized files
        assert mock_log.warning.call_count == 1

        # Should record finding to handoff
        mock_handoff_instance.append_current_handoff.assert_called_once()
        call_kwargs = mock_handoff_instance.append_current_handoff.call_args[1]
        assert "unauthorized commit" in call_kwargs["message"].lower()
        # Should mention the unauthorized file
        assert "src/vibe3/execution/codeagent_runner.py" in call_kwargs["message"]

    def test_planner_no_branch_skips_check(self) -> None:
        """Planner check skips if no branch provided."""
        service = CodeagentExecutionService()
        mock_log = MagicMock()

        # Should return early without any git operations
        service._check_planner_commits(
            commit_count_before=5,
            branch=None,
            actor="claude/sonnet",
            log=mock_log,
        )

        # Should not log anything
        mock_log.warning.assert_not_called()

    def test_planner_git_error_handled_gracefully(self) -> None:
        """Planner check handles git errors gracefully."""
        service = CodeagentExecutionService()
        mock_log = MagicMock()

        with patch(
            "vibe3.execution.codeagent_runner.GitClient"
        ) as mock_git_client_class:
            mock_git_client = MagicMock()
            mock_git_client._run.side_effect = Exception("git command failed")
            mock_git_client_class.return_value = mock_git_client

            # Should not raise any exception
            service._check_planner_commits(
                commit_count_before=5,
                branch="task/issue-42",
                actor="claude/sonnet",
                log=mock_log,
            )

        # Should log warning about git error
        mock_log.warning.assert_called_once()
        assert "Failed to check planner commits" in mock_log.warning.call_args[0][0]

    def test_planner_handoff_error_handled_gracefully(self) -> None:
        """Planner check handles handoff append errors gracefully."""
        service = CodeagentExecutionService()
        mock_log = MagicMock()

        with (
            patch(
                "vibe3.execution.codeagent_runner.GitClient"
            ) as mock_git_client_class,
            patch(
                "vibe3.services.handoff_service.HandoffService"
            ) as mock_handoff_class,
        ):
            mock_git_client = MagicMock()
            mock_git_client._run.side_effect = [
                "6",  # commit_count_after = 6
                "src/vibe3/execution/codeagent_runner.py",
            ]
            mock_git_client_class.return_value = mock_git_client

            mock_handoff_instance = MagicMock()
            mock_handoff_instance.append_current_handoff.side_effect = Exception(
                "handoff write failed"
            )
            mock_handoff_class.return_value = mock_handoff_instance

            # Should not raise any exception
            service._check_planner_commits(
                commit_count_before=5,
                branch="task/issue-42",
                actor="claude/sonnet",
                log=mock_log,
            )

        # Should log warnings about unauthorized files and handoff failure
        # 1 for unauthorized files + 1 for handoff
        assert mock_log.warning.call_count == 2
        last_call = mock_log.warning.call_args_list[-1]
        assert "Failed to record planner finding" in last_call[0][0]
