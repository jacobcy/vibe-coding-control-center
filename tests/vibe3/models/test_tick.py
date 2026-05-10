"""Tests for TickRequest and TickPlan models."""

from unittest.mock import MagicMock

from vibe3.models.tick import TickPhase, TickPlan, TickRequest, TickSource
from vibe3.prompts.models import (
    PromptMaterialSpec,
    PromptVariableSource,
    VariableSourceKind,
)


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
    """TickPlan should be derived from TickRequest with explicit material."""
    req = TickRequest(
        source=TickSource.MANUAL_SCAN,
        governance_material="roadmap-intake",
        supervisor_issue_numbers=[743],
    )
    plan = TickPlan.from_request(req, config=None)
    assert plan.governance_enabled
    assert plan.governance_material == "roadmap-intake"
    assert plan.supervisor_issues == [743]


def test_tick_plan_auto_select_governance_material():
    """TickPlan should auto-select governance material via rotation."""
    # Create mock config
    config = MagicMock()

    # Create mock material catalog with 3 materials
    material1 = PromptMaterialSpec(
        name="roadmap-intake",
        source=PromptVariableSource(kind=VariableSourceKind.LITERAL, value=""),
    )
    material2 = PromptMaterialSpec(
        name="roadmap-review",
        source=PromptVariableSource(kind=VariableSourceKind.LITERAL, value=""),
    )
    material3 = PromptMaterialSpec(
        name="roadmap-maintenance",
        source=PromptVariableSource(kind=VariableSourceKind.LITERAL, value=""),
    )

    # Mock _load_governance_material_catalog to return our test materials
    import vibe3.roles.governance as governance_module

    original_load = governance_module._load_governance_material_catalog
    governance_module._load_governance_material_catalog = lambda: (
        material1,
        material2,
        material3,
    )
    try:
        # Test rotation: tick_count=0 should select material1
        req1 = TickRequest(
            source=TickSource.HEARTBEAT,
            tick_id=1,
            phases=[TickPhase.GOVERNANCE],
        )
        plan1 = TickPlan.from_request(req1, config=config, tick_count=0)
        assert plan1.governance_enabled
        assert plan1.governance_material == "roadmap-intake"

        # Test rotation: tick_count=1 should select material2
        req2 = TickRequest(
            source=TickSource.HEARTBEAT,
            tick_id=2,
            phases=[TickPhase.GOVERNANCE],
        )
        plan2 = TickPlan.from_request(req2, config=config, tick_count=1)
        assert plan2.governance_material == "roadmap-review"

        # Test rotation: tick_count=2 should select material3
        req3 = TickRequest(
            source=TickSource.HEARTBEAT,
            tick_id=3,
            phases=[TickPhase.GOVERNANCE],
        )
        plan3 = TickPlan.from_request(req3, config=config, tick_count=2)
        assert plan3.governance_material == "roadmap-maintenance"

        # Test rotation wraps around: tick_count=3 should select material1 again
        req4 = TickRequest(
            source=TickSource.HEARTBEAT,
            tick_id=4,
            phases=[TickPhase.GOVERNANCE],
        )
        plan4 = TickPlan.from_request(req4, config=config, tick_count=3)
        assert plan4.governance_material == "roadmap-intake"
    finally:
        # Restore original function
        governance_module._load_governance_material_catalog = original_load


def test_tick_plan_empty_phases():
    """TickPlan with empty phases should create a no-op tick."""
    req = TickRequest(
        source=TickSource.MANUAL_SCAN,
        phases=[],
    )
    plan = TickPlan.from_request(req, config=None)
    assert not plan.governance_enabled
    assert plan.governance_material is None
    assert not plan.supervisor_enabled
    assert plan.supervisor_issues == []
