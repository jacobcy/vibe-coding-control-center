"""Unit tests for prompt_meta module."""

from vibe3.execution.prompt_meta import (
    PromptMeta,
    build_prompt_meta,
    collect_prompt_refs,
)


class TestCollectPromptRefs:
    """Tests for collect_prompt_refs function."""

    def test_none_flow_state_returns_empty(self) -> None:
        """None flow_state should return empty dict."""
        result = collect_prompt_refs(None, ref_keys=("plan_ref",))
        assert result == {}

    def test_empty_flow_state_returns_empty(self) -> None:
        """Empty flow_state should return empty dict."""
        result = collect_prompt_refs({}, ref_keys=("plan_ref",))
        assert result == {}

    def test_collects_present_keys(self) -> None:
        """Should collect only keys that exist in flow_state."""
        flow_state = {"plan_ref": "docs/plans/x.md", "other": "val"}
        result = collect_prompt_refs(flow_state, ref_keys=("plan_ref",))
        assert result == {"plan_ref": "docs/plans/x.md"}

    def test_skips_missing_keys(self) -> None:
        """Should skip keys not in flow_state."""
        flow_state = {"a": "1"}
        result = collect_prompt_refs(flow_state, ref_keys=("a", "b", "c"))
        assert result == {"a": "1"}

    def test_skips_falsy_values(self) -> None:
        """Should skip keys with falsy values."""
        flow_state = {"a": "", "b": None, "c": 0}
        result = collect_prompt_refs(flow_state, ref_keys=("a", "b", "c"))
        assert result == {}

    def test_coerces_to_str(self) -> None:
        """Should coerce values to strings."""
        flow_state = {"a": 42}
        result = collect_prompt_refs(flow_state, ref_keys=("a",))
        assert result == {"a": "42"}


class TestBuildPromptMeta:
    """Tests for build_prompt_meta factory function."""

    def test_first_run_no_session(self) -> None:
        """First run with no session should use default mode and bootstrap."""
        meta = build_prompt_meta(
            None,
            ref_keys=("plan_ref",),
            retry_ref_keys=("retry_ref",),
            session_id=None,
            default_mode="default",
        )
        assert meta.prompt_mode == "default"
        assert meta.context_mode == "bootstrap"

    def test_retry_no_session(self) -> None:
        """Retry with no session should use retry mode and bootstrap."""
        flow_state = {"retry_ref": "docs/retries/x.md"}
        meta = build_prompt_meta(
            flow_state,
            ref_keys=("plan_ref", "retry_ref"),
            retry_ref_keys=("retry_ref",),
            session_id=None,
            default_mode="default",
        )
        assert meta.prompt_mode == "retry"
        assert meta.context_mode == "bootstrap"

    def test_retry_with_session(self) -> None:
        """Retry with session should use retry mode and resume."""
        flow_state = {"retry_ref": "docs/retries/x.md"}
        meta = build_prompt_meta(
            flow_state,
            ref_keys=("plan_ref", "retry_ref"),
            retry_ref_keys=("retry_ref",),
            session_id="abc",
            default_mode="default",
        )
        assert meta.prompt_mode == "retry"
        assert meta.context_mode == "resume"

    def test_first_run_with_session(self) -> None:
        """First run with session should use default mode and bootstrap."""
        meta = build_prompt_meta(
            None,
            ref_keys=("plan_ref",),
            retry_ref_keys=("retry_ref",),
            session_id="abc",
            default_mode="default",
        )
        assert meta.prompt_mode == "default"
        assert meta.context_mode == "bootstrap"

    def test_custom_modes(self) -> None:
        """Should use custom mode strings."""
        flow_state = {"retry_ref": "docs/retries/x.md"}
        meta = build_prompt_meta(
            flow_state,
            ref_keys=("plan_ref", "retry_ref"),
            retry_ref_keys=("retry_ref",),
            session_id=None,
            default_mode="plan",
            retry_mode="replan",
        )
        assert meta.prompt_mode == "replan"

    def test_refs_passed_through(self) -> None:
        """Should pass refs through to PromptMeta."""
        flow_state = {"plan_ref": "docs/plans/x.md", "other": "val"}
        meta = build_prompt_meta(
            flow_state,
            ref_keys=("plan_ref", "other"),
            retry_ref_keys=("retry_ref",),
            session_id=None,
            default_mode="default",
        )
        assert meta.refs == {"plan_ref": "docs/plans/x.md", "other": "val"}


class TestPromptMetaProperties:
    """Tests for PromptMeta computed properties."""

    def test_include_global_notice_true_by_default(self) -> None:
        """Default configuration should include global notice."""
        meta = PromptMeta(
            prompt_mode="default",
            context_mode="bootstrap",
            session_id=None,
            refs={},
        )
        assert meta.include_global_notice is True

    def test_include_global_notice_false_when_retry_resume(self) -> None:
        """Retry with resume should not include global notice."""
        meta = PromptMeta(
            prompt_mode="retry",
            context_mode="resume",
            session_id="abc",
            refs={},
        )
        assert meta.include_global_notice is False

    def test_include_global_notice_true_when_retry_bootstrap(self) -> None:
        """Retry with bootstrap should still include global notice."""
        meta = PromptMeta(
            prompt_mode="retry",
            context_mode="bootstrap",
            session_id=None,
            refs={},
        )
        assert meta.include_global_notice is True

    def test_fallback_context_mode_resume_to_bootstrap(self) -> None:
        """Resume mode should fallback to bootstrap."""
        meta = PromptMeta(
            prompt_mode="default",
            context_mode="resume",
            session_id="abc",
            refs={},
        )
        assert meta.fallback_context_mode == "bootstrap"

    def test_fallback_context_mode_none_for_bootstrap(self) -> None:
        """Bootstrap mode should have no fallback."""
        meta = PromptMeta(
            prompt_mode="default",
            context_mode="bootstrap",
            session_id=None,
            refs={},
        )
        assert meta.fallback_context_mode is None

    def test_session_reused_true(self) -> None:
        """Session should be reused when session_id exists and mode is resume."""
        meta = PromptMeta(
            prompt_mode="retry",
            context_mode="resume",
            session_id="abc",
            refs={},
        )
        assert meta.session_reused is True

    def test_session_reused_false_no_session(self) -> None:
        """Session should not be reused without session_id."""
        meta = PromptMeta(
            prompt_mode="retry",
            context_mode="resume",
            session_id=None,
            refs={},
        )
        assert meta.session_reused is False

    def test_session_reused_false_bootstrap_mode(self) -> None:
        """Session should not be reused in bootstrap mode."""
        meta = PromptMeta(
            prompt_mode="default",
            context_mode="bootstrap",
            session_id="abc",
            refs={},
        )
        assert meta.session_reused is False


class TestPromptMetaSummary:
    """Tests for PromptMeta.summary method."""

    def test_summary_includes_fallback(self) -> None:
        """Summary should include fallback_context_mode when it exists."""
        meta = PromptMeta(
            prompt_mode="retry",
            context_mode="resume",
            session_id="abc",
            refs={},
        )
        summary = meta.summary(sections=["section1"])
        assert "fallback_context_mode" in summary
        assert summary["fallback_context_mode"] == "bootstrap"

    def test_summary_excludes_fallback(self) -> None:
        """Summary should exclude fallback_context_mode when it's None."""
        meta = PromptMeta(
            prompt_mode="default",
            context_mode="bootstrap",
            session_id=None,
            refs={},
        )
        summary = meta.summary(sections=["section1"])
        assert "fallback_context_mode" not in summary

    def test_summary_fields(self) -> None:
        """Summary should include all expected fields."""
        meta = PromptMeta(
            prompt_mode="retry",
            context_mode="resume",
            session_id="abc",
            refs={"plan_ref": "docs/plans/x.md"},
        )
        summary = meta.summary(sections=["section1", "section2"])

        assert summary["prompt_mode"] == "retry"
        assert summary["context_mode"] == "resume"
        assert summary["session_reused"] is True
        assert summary["session_id"] == "abc"
        assert summary["sections"] == ["section1", "section2"]
        assert summary["refs"] == {"plan_ref": "docs/plans/x.md"}
        assert summary["fallback_context_mode"] == "bootstrap"
