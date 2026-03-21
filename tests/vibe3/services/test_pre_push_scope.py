"""Tests for pre-push review scope resolution."""

from unittest.mock import MagicMock, patch

from vibe3.services.pre_push_scope import resolve_pre_push_scope


ZERO_SHA = "0" * 40


class TestResolvePrePushScope:
    """Verify pre-push review only considers refs introduced by this push."""

    def test_uses_remote_sha_for_existing_branch_push(self) -> None:
        scope = resolve_pre_push_scope(
            (
                "refs/heads/task/demo "
                "1111111111111111111111111111111111111111 "
                "refs/heads/task/demo "
                "2222222222222222222222222222222222222222\n"
            )
        )

        assert scope.base_ref == "2222222222222222222222222222222222222222"
        assert scope.head_ref == "1111111111111111111111111111111111111111"
        assert scope.is_incremental is True
        assert "this push only" in scope.summary

    def test_falls_back_to_mainline_for_new_branch_push(self) -> None:
        scope = resolve_pre_push_scope(
            (
                "refs/heads/task/demo "
                "1111111111111111111111111111111111111111 "
                "refs/heads/task/demo "
                f"{ZERO_SHA}\n"
            )
        )

        assert scope.base_ref == "origin/main"
        assert scope.head_ref == "1111111111111111111111111111111111111111"
        assert scope.is_incremental is False
        assert "new branch push" in scope.summary

    def test_ignores_delete_updates_and_uses_next_valid_ref(self) -> None:
        scope = resolve_pre_push_scope(
            (
                f"refs/heads/task/old {ZERO_SHA} refs/heads/task/old "
                "3333333333333333333333333333333333333333\n"
                "refs/heads/task/demo "
                "1111111111111111111111111111111111111111 "
                "refs/heads/task/demo "
                "2222222222222222222222222222222222222222\n"
            )
        )

        assert scope.base_ref == "2222222222222222222222222222222222222222"
        assert scope.head_ref == "1111111111111111111111111111111111111111"

    @patch("vibe3.clients.git_client.GitClient")
    def test_infers_incremental_push_from_git_state(self, mock_git_client: MagicMock) -> None:
        """When stdin is empty, infer incremental push from git state."""
        # Mock git client
        mock_instance = MagicMock()
        mock_instance.get_current_branch.return_value = "task/demo"
        mock_instance._run.return_value = "abc123"  # Remote branch exists
        mock_git_client.return_value = mock_instance

        scope = resolve_pre_push_scope("")

        assert scope.base_ref == "origin/task/demo"
        assert scope.is_incremental is True
        assert "inferred incremental push" in scope.summary

    @patch("vibe3.clients.git_client.GitClient")
    def test_infers_new_branch_push_from_git_state(
        self, mock_git_client: MagicMock
    ) -> None:
        """When stdin is empty and remote branch doesn't exist, infer new branch push."""
        # Mock git client
        mock_instance = MagicMock()
        mock_instance.get_current_branch.return_value = "task/demo"
        mock_instance._run.side_effect = Exception("Remote branch not found")
        mock_git_client.return_value = mock_instance

        scope = resolve_pre_push_scope("")

        assert scope.base_ref == "origin/main"
        assert scope.is_incremental is False
        assert "inferred new branch push" in scope.summary

