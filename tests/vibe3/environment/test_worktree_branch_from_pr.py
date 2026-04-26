"""Unit tests for branch-from-PR creation in WorktreeManager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.worktree import WorktreeManager


class TestFindDependencyWakeupPR:
    """Tests for _find_dependency_wakeup_pr method."""

    def test_no_wakeup_event_returns_none(self) -> None:
        """When no dependency_wake_up event, return None."""
        # Setup
        import time

        unique_id = int(time.time() * 1000)
        branch = f"task/issue-300-{unique_id}"

        store = SQLiteClient()
        store.update_flow_state(branch, flow_slug=f"test-300-{unique_id}")
        store.add_event(
            branch,
            "planner_started",
            "manager",
            detail="Planning started",
        )

        # Mock manager with real Path
        config = MagicMock()
        repo_path = Path("/tmp/test-repo")
        manager = WorktreeManager(config=config, repo_path=repo_path)

        with patch(
            "vibe3.environment.worktree_pr_mixin.SQLiteClient",
            return_value=store,
        ):
            # Execute
            result = manager._find_dependency_wakeup_pr(branch)

            # Verify
            assert result is None

    def test_wakeup_event_with_source_pr_returns_pr_number(self) -> None:
        """When wake-up event with source_pr exists, return PR number."""
        # Setup
        store = SQLiteClient()
        store.update_flow_state("task/issue-300", flow_slug="test-300")
        store.add_event(
            "task/issue-300",
            "flow_unblocked",
            "orchestra:dependency_handler",
            detail="Dependencies satisfied",
            refs={"source_pr": "42"},
        )

        # Mock manager with real Path for repo_path
        config = MagicMock()
        repo_path = Path("/tmp/test-repo")
        manager = WorktreeManager(config=config, repo_path=repo_path)

        with patch(
            "vibe3.environment.worktree_pr_mixin.SQLiteClient",
            return_value=store,
        ):
            # Execute
            result = manager._find_dependency_wakeup_pr("task/issue-300")

            # Verify
            assert result == 42

    def test_multiple_wakeup_events_returns_most_recent(self) -> None:
        """When multiple wake-up events, pick the most recent source PR."""
        # Setup
        import time

        unique_id = int(time.time() * 1000)
        branch = f"task/issue-300-{unique_id}"

        store = SQLiteClient()
        store.update_flow_state(branch, flow_slug=f"test-300-{unique_id}")
        # First wake-up from PR 42
        store.add_event(
            branch,
            "flow_unblocked",
            "orchestra:dependency_handler",
            detail="Dependencies satisfied",
            refs={"source_pr": "42"},
        )
        # Later wake-up from PR 43
        store.add_event(
            branch,
            "flow_unblocked",
            "orchestra:dependency_handler",
            detail="Dependencies satisfied (another dependency)",
            refs={"source_pr": "43"},
        )

        # Mock manager with real Path
        config = MagicMock()
        repo_path = Path("/tmp/test-repo")
        manager = WorktreeManager(config=config, repo_path=repo_path)

        with patch(
            "vibe3.environment.worktree_pr_mixin.SQLiteClient",
            return_value=store,
        ):
            # Execute
            result = manager._find_dependency_wakeup_pr(branch)

            # Verify
            assert result == 43

    def test_wakeup_event_no_source_pr_returns_none(self) -> None:
        """When wake-up event has no source_pr, return None."""
        # Setup
        import time

        unique_id = int(time.time() * 1000)
        branch = f"task/issue-300-{unique_id}"

        store = SQLiteClient()
        store.update_flow_state(branch, flow_slug=f"test-300-{unique_id}")
        store.add_event(
            branch,
            "flow_unblocked",
            "orchestra:dependency_handler",
            detail="Dependencies satisfied",
            refs={},  # No source_pr
        )

        # Mock manager with real Path
        config = MagicMock()
        repo_path = Path("/tmp/test-repo")
        manager = WorktreeManager(config=config, repo_path=repo_path)

        with patch(
            "vibe3.environment.worktree_pr_mixin.SQLiteClient",
            return_value=store,
        ):
            # Execute
            result = manager._find_dependency_wakeup_pr(branch)

            # Verify
            assert result is None


class TestFetchPRBranch:
    """Tests for _fetch_pr_branch method."""

    def test_pr_not_found_returns_none(self) -> None:
        """When PR doesn't exist, return None."""
        # Setup
        config = MagicMock()
        manager = WorktreeManager(config=config, repo_path=MagicMock())

        with patch("vibe3.environment.worktree_pr_mixin.GitHubClient") as mock_gh_cls:
            mock_gh = MagicMock()
            mock_gh.get_pr.return_value = None
            mock_gh_cls.return_value = mock_gh

            # Execute
            result = manager._fetch_pr_branch(999)

            # Verify
            assert result is None
            mock_gh.get_pr.assert_called_once_with(pr_number=999)

    def test_pr_found_returns_head_branch_after_successful_fetch(self) -> None:
        """When PR exists and fetch succeeds, return head branch name."""
        # Setup
        config = MagicMock()
        repo_path = MagicMock()
        manager = WorktreeManager(config=config, repo_path=repo_path)

        # Mock PR response
        mock_pr = MagicMock()
        mock_pr.head_branch = "feature/dependency-work"

        with patch("vibe3.environment.worktree_pr_mixin.GitHubClient") as mock_gh_cls:
            mock_gh = MagicMock()
            mock_gh.get_pr.return_value = mock_pr
            mock_gh_cls.return_value = mock_gh

            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0

                # Execute
                result = manager._fetch_pr_branch(42)

                # Verify
                assert result == "feature/dependency-work"
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert "git" in args
                assert "fetch" in args
                assert "origin" in args
                assert any("feature/dependency-work" in arg for arg in args)


class TestCreateFromPRBranch:
    """Tests for _create_from_pr_branch integration."""

    def test_fetch_failure_returns_none(self) -> None:
        """When fetch fails, return None to trigger fallback."""
        # Setup
        config = MagicMock()
        repo_path = MagicMock()
        manager = WorktreeManager(config=config, repo_path=repo_path)

        with patch("vibe3.environment.worktree_pr_mixin.GitHubClient") as mock_gh_cls:
            mock_gh = MagicMock()
            mock_gh.get_pr.return_value = None
            mock_gh_cls.return_value = mock_gh

            # Execute
            result = manager._create_from_pr_branch(
                MagicMock(), "task/issue-300", 300, 42
            )

            # Verify
            assert result is None


class TestCreateFromPRBranchExistingBranch:
    """Tests for _create_from_pr_branch when branch already exists locally."""

    def test_existing_branch_update_ref_success(self) -> None:
        """When branch exists and update-ref succeeds, attach worktree."""
        from pathlib import Path

        config = MagicMock()
        repo_path = Path("/tmp/test-repo")
        manager = WorktreeManager(config=config, repo_path=repo_path)

        mock_pr = MagicMock()
        mock_pr.head_branch = "feature/dep-work"

        with patch("vibe3.environment.worktree_pr_mixin.GitHubClient") as mock_gh_cls:
            mock_gh = MagicMock()
            mock_gh.get_pr.return_value = mock_pr
            mock_gh_cls.return_value = mock_gh

            with patch.object(manager, "_branch_exists_locally", return_value=True):
                with patch("vibe3.environment.worktree_support.find_worktree_by_path"):
                    with patch(
                        "vibe3.environment.worktree_support.initialize_worktree"
                    ):
                        with patch("shutil.rmtree"):
                            # Mock _fetch_pr_branch to return head_branch directly
                            with patch.object(
                                manager,
                                "_fetch_pr_branch",
                                return_value="feature/dep-work",
                            ):
                                # Mock update-ref + worktree add separately
                                with patch(
                                    "vibe3.environment.worktree_pr_mixin.subprocess"
                                ) as mock_subprocess:
                                    mock_subprocess.run.side_effect = [
                                        MagicMock(returncode=0),  # prune
                                        MagicMock(returncode=0),  # update-ref
                                        MagicMock(returncode=0),  # worktree add
                                    ]

                                    result = manager._create_from_pr_branch(
                                        Path(
                                            "/tmp/test-repo/.worktrees/task/issue-300"
                                        ),
                                        "task/issue-300",
                                        300,
                                        42,
                                    )

                                    assert result is not None
                                    assert result.branch == "task/issue-300"

                                    # Verify update-ref was called
                                    calls = mock_subprocess.run.call_args_list
                                    update_ref_call = calls[1]
                                    assert "update-ref" in update_ref_call[0][0]

                                    # Verify worktree add used existing
                                    # branch (no -b flag)
                                    add_call = calls[2]
                                    add_args = add_call[0][0]
                                    assert "-b" not in add_args
                                    assert "task/issue-300" in add_args

    def test_existing_branch_update_ref_failure_returns_none(self) -> None:
        """When branch exists but update-ref fails, return None for fallback."""
        from pathlib import Path

        config = MagicMock()
        repo_path = Path("/tmp/test-repo")
        manager = WorktreeManager(config=config, repo_path=repo_path)

        mock_pr = MagicMock()
        mock_pr.head_branch = "feature/dep-work"

        with patch("vibe3.environment.worktree_pr_mixin.GitHubClient") as mock_gh_cls:
            mock_gh = MagicMock()
            mock_gh.get_pr.return_value = mock_pr
            mock_gh_cls.return_value = mock_gh

            with patch.object(manager, "_branch_exists_locally", return_value=True):
                with patch("vibe3.environment.worktree_support.find_worktree_by_path"):
                    with patch("shutil.rmtree"):
                        with patch.object(
                            manager,
                            "_fetch_pr_branch",
                            return_value="feature/dep-work",
                        ):
                            with patch(
                                "vibe3.environment.worktree_pr_mixin.subprocess"
                            ) as mock_subprocess:
                                mock_subprocess.run.side_effect = [
                                    MagicMock(returncode=0),  # prune
                                    MagicMock(
                                        returncode=1,
                                        stderr="ref lock failed",
                                    ),  # update-ref fails
                                ]

                                result = manager._create_from_pr_branch(
                                    Path("/tmp/test-repo/.worktrees/task/issue-300"),
                                    "task/issue-300",
                                    300,
                                    42,
                                )

                                # Should return None (trigger fallback),
                                # not silently proceed with wrong tip
                                assert result is None
