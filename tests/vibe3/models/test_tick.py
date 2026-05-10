"""Tests for TickRequest and TickPlan models."""

from vibe3.models.tick import TickPhase, TickPlan, TickRequest, TickSource


def test_tick_request_manual_defaults():
    """Manual tick should default to tick_id=0 and both phases enabled."""
    req = TickRequest(source=TickSource.MANUAL_SCAN)
    assert req.tick_id == 0
    assert TickPhase.GOVERNANCE in req.phases
    assert TickPhase.SUPERVISOR in req.phases
    assert req.governance_material is None
    assert req.supervisor_issue_numbers == []


def test_tick_request_with_governance_material():
    """Should accept explicit governance material."""
    req = TickRequest(
        source=TickSource.MANUAL_SCAN,
        governance_material="roadmap-intake",
        phases=[TickPhase.GOVERNANCE],
    )
    assert req.governance_material == "roadmap-intake"
    assert TickPhase.SUPERVISOR not in req.phases


def test_tick_request_with_supervisor_issues():
    """Should accept explicit supervisor issue numbers."""
    req = TickRequest(
        source=TickSource.MANUAL_SCAN,
        supervisor_issue_numbers=[743, 812],
        phases=[TickPhase.SUPERVISOR],
    )
    assert req.supervisor_issue_numbers == [743, 812]


def test_tick_plan_from_request():
    """TickPlan should be derived from TickRequest."""
    req = TickRequest(
        source=TickSource.MANUAL_SCAN,
        governance_material="roadmap-intake",
        supervisor_issue_numbers=[743],
    )
    plan = TickPlan.from_request(req, config=None)
    assert plan.governance_enabled
    assert plan.governance_material == "roadmap-intake"
    assert plan.supervisor_issues == [743]
