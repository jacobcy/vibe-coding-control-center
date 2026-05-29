"""Test FlowManager migration to domain layer."""


def test_flow_manager_importable_from_domain():
    """Verify FlowManager can be imported from domain.flow_manager."""
    from vibe3.domain.flow_manager import FlowManager

    assert FlowManager is not None
    assert hasattr(FlowManager, "__init__")
    assert hasattr(FlowManager, "get_flow_for_issue")
    assert hasattr(FlowManager, "create_flow_for_issue")


def test_flow_manager_importable_from_domain_init():
    """Verify FlowManager is exported from domain.__init__."""
    from vibe3.domain import FlowManager

    assert FlowManager is not None
