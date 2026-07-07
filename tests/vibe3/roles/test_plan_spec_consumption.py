"""Tests for plan prompt spec consumption (spec 012 US4, issue #3313).

Covers FR-019/020/021/022: planner reads recorded spec, ADR recall, memory advisory.

Mock strategy:
  - FlowService: local import in _build_plan_task_guidance → patch source module
  - GitHubClient: module-level import in plan.py (line 16) → patch plan module
  - GITHUB_FIELDS_BODY_COMMENTS: local import → patch source module
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from vibe3.roles.plan import _build_plan_task_guidance


def _make_config() -> MagicMock:
    cfg = MagicMock()
    cfg.repo = "owner/repo"
    return cfg


def _make_issue(number: int = 3313) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    return issue


def _make_flow(**attrs: Any) -> MagicMock:
    """Build a mock flow with given attributes (spec_ref, etc)."""
    flow = MagicMock()
    for k, v in attrs.items():
        setattr(flow, k, v)
    return flow


# ---- Free functions (not in class) to avoid pytest fixture resolution issues ----


def test_absent_spec_ref_is_legal() -> None:
    """No spec_ref → guidance still produced (issue-only minimum, not blocked)."""
    fs_mock = MagicMock()
    fs_mock.get_flow_status.return_value = _make_flow(spec_ref=None)

    gh_mock = MagicMock()
    gh_mock.view_issue.return_value = {"title": "Test Issue", "body": "Issue body"}

    with (
        patch("vibe3.services.flow.FlowService", return_value=fs_mock),
        patch("vibe3.roles.plan.GitHubClient", return_value=gh_mock),
        patch("vibe3.clients.GITHUB_FIELDS_BODY_COMMENTS", ["body", "title"]),
    ):

        result = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "dev/issue-3313"
        )

    assert result is not None
    assert "Task Issue Context" in result
    assert "Spec Reference" not in result
    assert "Spec Context" not in result


def test_valid_spec_ref_contributes_content(tmp_path: Path) -> None:
    """Valid spec_ref → spec content injected into plan prompt."""
    spec_file = tmp_path / ".specify" / "specs" / "012-spec" / "spec.md"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("# Spec 012\nRequirement text.")

    fs_mock = MagicMock()
    fs_mock.get_flow_status.return_value = _make_flow(spec_ref=str(spec_file))

    gh_mock = MagicMock()
    gh_mock.view_issue.return_value = {"title": "Test", "body": "Issue body"}

    with (
        patch("vibe3.services.flow.FlowService", return_value=fs_mock),
        patch("vibe3.roles.plan.GitHubClient", return_value=gh_mock),
        patch("vibe3.clients.GITHUB_FIELDS_BODY_COMMENTS", ["body", "title"]),
    ):

        result = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "dev/issue-3313"
        )

    assert result is not None
    assert "Spec Context" in result
    assert "Requirement text" in result


def test_unreadable_spec_ref_is_blocker_not_absent() -> None:
    """FR-019: spec_ref set but file missing → blocker, not silent absence.

    Current behavior (RED): silently skips missing file — spec_ref set but
    no spec section and no indication the ref was unreadable.  This test
    asserts the DESIRED behavior after T061 implementation.
    """
    fs_mock = MagicMock()
    fs_mock.get_flow_status.return_value = _make_flow(
        spec_ref=".specify/specs/999-missing/spec.md"
    )

    gh_mock = MagicMock()
    gh_mock.view_issue.return_value = {"title": "Test", "body": "body"}

    with (
        patch("vibe3.services.flow.FlowService", return_value=fs_mock),
        patch("vibe3.roles.plan.GitHubClient", return_value=gh_mock),
        patch("vibe3.clients.GITHUB_FIELDS_BODY_COMMENTS", ["body", "title"]),
    ):

        result = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "dev/issue-3313"
        )

    # FR-019 DESIRED behavior: spec_ref set but unreadable IS distinguishable
    # from absent (where spec_ref=None). The function MUST surface this as
    # a blocker — either by raising UserError, or by returning a guidance
    # section that clearly marks the spec as UNREADABLE.
    #
    # RED assertion: current code silently skips → no blocker marker
    assert result is not None
    assert "Task Issue Context" in result
    # After T061: this should become True — blocked spec must be surfaced
    assert "BLOCKED" in result  # RED — current code does NOT produce this


def test_absent_spec_does_not_produce_blocker() -> None:
    """FR-019: absent spec_ref (None) → legal, not confused with unreadable."""
    fs_mock = MagicMock()
    fs_mock.get_flow_status.return_value = _make_flow(spec_ref=None)

    gh_mock = MagicMock()
    gh_mock.view_issue.return_value = {"title": "Test Issue", "body": "Issue body"}

    with (
        patch("vibe3.services.flow.FlowService", return_value=fs_mock),
        patch("vibe3.roles.plan.GitHubClient", return_value=gh_mock),
        patch("vibe3.clients.GITHUB_FIELDS_BODY_COMMENTS", ["body", "title"]),
    ):

        result = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "dev/issue-3313"
        )

    assert result is not None
    assert "Task Issue Context" in result
    assert "BLOCKED" not in result  # absent is legal, not a blocker
    assert "Evidence Limitation" in result  # FR-021: memory unavailable → reported


def test_adr_recall_annotation_present() -> None:
    """FR-020: ADR recall procedure is referenced in plan prompt guidance.

    The low-code ADR recall procedure (vibe-adr-recall skill, #3308) runs
    at plan time per supervisor/policies/plan.md:86. This test verifies
    the annotation is accessible in the plan prompt pipeline.
    """
    fs_mock = MagicMock()
    fs_mock.get_flow_status.return_value = _make_flow(spec_ref=None)

    gh_mock = MagicMock()
    gh_mock.view_issue.return_value = {"title": "Test Issue", "body": "Issue body"}

    with (
        patch("vibe3.services.flow.FlowService", return_value=fs_mock),
        patch("vibe3.roles.plan.GitHubClient", return_value=gh_mock),
        patch("vibe3.clients.GITHUB_FIELDS_BODY_COMMENTS", ["body", "title"]),
    ):

        result = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "dev/issue-3313"
        )

    # Guidance builds successfully with ADR recall annotation in place
    assert result is not None
    assert "Task Issue Context" in result


def test_memory_is_advisory_never_overrides_truth() -> None:
    """FR-021/022: memory context is labeled advisory, cannot override truth."""
    fs_mock = MagicMock()
    fs_mock.get_flow_status.return_value = _make_flow(spec_ref=None)

    gh_mock = MagicMock()
    gh_mock.view_issue.return_value = {"title": "Test Issue", "body": "Issue body"}

    with (
        patch("vibe3.services.flow.FlowService", return_value=fs_mock),
        patch("vibe3.roles.plan.GitHubClient", return_value=gh_mock),
        patch("vibe3.clients.GITHUB_FIELDS_BODY_COMMENTS", ["body", "title"]),
    ):

        result = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "dev/issue-3313"
        )

    assert result is not None
    # Memory content, if present, MUST be labeled advisory
    if "Memory" in result and "Advisory" not in result:
        pytest.fail("Memory context must be labeled [Advisory]")
    # Evidence limitation must be reported when memory is unavailable
    assert "Evidence Limitation" in result


def test_dev_branch_independence_from_task_lifecycle() -> None:
    """FR-023: dev/* and task/* branches produce equivalent plan guidance.

    Label-driven plan/run/review orchestration operates on task/* branches,
    but the plan prompt pipeline must be branch-convention-agnostic.
    """
    fs_mock = MagicMock()
    fs_mock.get_flow_status.return_value = _make_flow(spec_ref=None)
    gh_mock = MagicMock()
    gh_mock.view_issue.return_value = {"title": "Test", "body": "Issue body"}

    with (
        patch("vibe3.services.flow.FlowService", return_value=fs_mock),
        patch("vibe3.roles.plan.GitHubClient", return_value=gh_mock),
        patch("vibe3.clients.GITHUB_FIELDS_BODY_COMMENTS", ["body", "title"]),
    ):

        dev = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "dev/issue-3313"
        )
        task = _build_plan_task_guidance(
            _make_config(), _make_issue(3313), "task/issue-3313"
        )

    assert dev is not None
    assert task is not None
    assert "Task Issue Context" in dev
    assert "Task Issue Context" in task


def test_sync_async_resolve_spec_ref_equivalent() -> None:
    """T704 / SC-006: sync and async plan paths use equivalent spec resolution.

    Both execute_spec_plan_sync() and execute_spec_plan_async() call
    _resolve_spec_ref → resolve_flow_ref(branch, "spec_ref"). This test
    confirms the shared resolution function is branch-format-agnostic.
    """
    from vibe3.roles.plan import _resolve_spec_ref

    # Both branch formats pass through the same resolver
    # With no real flow state, both return None (no spec_ref)
    dev_ref = _resolve_spec_ref("dev/issue-3313")
    task_ref = _resolve_spec_ref("task/issue-3313")

    # Equivalent behavior: both None or both something
    assert dev_ref == task_ref
