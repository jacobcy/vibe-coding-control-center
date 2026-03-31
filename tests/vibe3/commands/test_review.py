"""Tests for review command assembler integration."""

from __future__ import annotations

from unittest.mock import patch


class TestReviewContextBuilderUsesAssembler:
    """Assert review context builders go through PromptAssembler."""

    def test_make_review_context_builder_calls_body_builder(self) -> None:
        """make_review_context_builder should invoke build_review_prompt_body."""
        from vibe3.config.settings import VibeConfig
        from vibe3.models.review import ReviewRequest, ReviewScope
        from vibe3.services.context_builder import make_review_context_builder

        config = VibeConfig.get_defaults()
        request = ReviewRequest(scope=ReviewScope.for_base("main"))
        with patch(
            "vibe3.services.context_builder.build_review_prompt_body",
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
        import vibe3.services.context_builder as mod

        assert not hasattr(
            mod, "build_review_context"
        ), "build_review_context should be deleted; use build_review_prompt_body"

    def test_review_usecase_context_builder_uses_assembler(self) -> None:
        """ReviewUsecase should build context through assembler-backed callable."""
        from vibe3.agents.review_agent import ReviewUsecase
        from vibe3.services.context_builder import make_review_context_builder

        usecase = ReviewUsecase()
        # The default context_builder should be make_review_context_builder
        assert usecase.context_builder is make_review_context_builder
