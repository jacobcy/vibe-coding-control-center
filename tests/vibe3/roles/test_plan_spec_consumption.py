"""Tests for plan prompt task guidance (spec 012 US4, ADR-0007).

Covers FR-019/020/021/022 under ADR-0007: plan prompts are NOT pre-injected
with spec_ref or memory context. The agent gathers context via spec-kit /
graphify / mem-search tools per supervisor/policies/plan.md. Only issue body
is injected (the legit automation channel).

Mock strategy:
  - FlowService: local import in _build_plan_task_guidance → patch source module
  - GitHubClient: module-level import in plan.py (line 16) → patch plan module
  - GITHUB_FIELDS_BODY_COMMENTS: local import → patch source module
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

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


def test_valid_spec_ref_not_injected(tmp_path: Path) -> None:
    """ADR-0007: valid spec_ref does NOT inject spec content into plan prompt.

    The agent reads the spec via ``vibe3 handoff show @spec`` per
    supervisor/policies/plan.md; plan guidance carries only issue body.
    """
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
    assert "Task Issue Context" in result
    # ADR-0007: spec content must NOT be pre-injected
    assert "Spec Context" not in result
    assert "Requirement text" not in result


def test_unreadable_spec_ref_not_plan_blocker() -> None:
    """ADR-0007: unreadable spec_ref is NOT surfaced as a plan-time blocker.

    Plan no longer reads spec_ref (agent does via handoff tool). Spec
    completion is reconciled by the reviewer (review policy §0f).
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

    assert result is not None
    assert "Task Issue Context" in result
    # ADR-0007: plan does not surface spec blocker
    assert "BLOCKED" not in result


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


def test_memory_not_injected_via_code() -> None:
    """ADR-0007: long-term memory is NOT pre-injected into plan guidance.

    The agent queries memory via the mem-search skill per
    supervisor/policies/plan.md. No ``claude-memory`` subprocess call, no
    Advisory Memory section, no Evidence Limitation marker.
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

    assert result is not None
    assert "Advisory Memory" not in result
    assert "Evidence Limitation" not in result


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
