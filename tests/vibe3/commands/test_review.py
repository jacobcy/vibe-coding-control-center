"""Tests for review command assembler integration."""

from __future__ import annotations

from unittest.mock import patch


class TestReviewContextBuilderUsesAssembler:
    """Assert review context builders go through PromptAssembler."""

    def test_make_review_context_builder_calls_body_builder(self) -> None:
        """make_review_context_builder should invoke build_review_prompt_body."""
        from vibe3.agents.review_prompt import make_review_context_builder
        from vibe3.config.settings import VibeConfig
        from vibe3.models.review import ReviewRequest, ReviewScope

        config = VibeConfig.get_defaults()
        request = ReviewRequest(scope=ReviewScope.for_base("main"))
        with patch(
            "vibe3.agents.review_prompt.build_review_prompt_body",
            return_value="assembled review body",
        ):
            cb = make_review_context_builder(request, config)
            text = cb()

        assert text == "assembled review body"
        assert cb.last_result is not None
        assert cb.last_result.recipe_key == "review.default"

    def test_review_context_builder_no_longer_exports_build_review_context(
        self,
    ) -> None:
        """build_review_context (old name) must not exist as public API."""
        import vibe3.agents.review_prompt as mod

        assert not hasattr(
            mod, "build_review_context"
        ), "build_review_context should be deleted; use build_review_prompt_body"

    def test_execute_manual_review_lives_in_role_layer(self) -> None:
        """Manual review execution should now be owned by roles.review."""
        import vibe3.roles.review as mod

        assert hasattr(mod, "execute_manual_review")
