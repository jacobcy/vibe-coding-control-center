"""Tests for pre-push review scope resolution."""

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

