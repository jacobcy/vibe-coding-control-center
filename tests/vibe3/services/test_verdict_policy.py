"""Tests for review verdict policy helpers."""

from vibe3.services.shared.verdicts import (
    ALL_VERDICTS,
    blocks_merge,
    passes_review,
    requires_audit_ref,
)


def test_pass_and_minor_are_passing_verdicts() -> None:
    assert passes_review("PASS") is True
    assert passes_review("MINOR") is True
    assert passes_review("MAJOR") is False


def test_only_actionable_verdicts_require_audit_ref() -> None:
    assert requires_audit_ref("MINOR") is True
    assert requires_audit_ref("MAJOR") is True
    assert requires_audit_ref("BLOCK") is True
    assert requires_audit_ref("PASS") is False
    assert requires_audit_ref("REFUSE") is False


def test_refuse_blocks_merge_but_does_not_require_audit_ref() -> None:
    assert blocks_merge("MAJOR") is True
    assert blocks_merge("BLOCK") is True
    assert blocks_merge("REFUSE") is True
    assert blocks_merge("PASS") is False


def test_verdict_policy_includes_new_values() -> None:
    assert "MINOR" in ALL_VERDICTS
    assert "REFUSE" in ALL_VERDICTS
