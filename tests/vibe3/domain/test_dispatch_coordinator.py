"""Test GlobalDispatchCoordinator migration to domain layer."""


def test_dispatch_coordinator_importable_from_domain():
    """Verify GlobalDispatchCoordinator can be imported from domain."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator

    assert GlobalDispatchCoordinator is not None
    assert hasattr(GlobalDispatchCoordinator, "__init__")
    assert hasattr(GlobalDispatchCoordinator, "coordinate")


def test_dispatch_coordinator_importable_from_domain_init():
    """Verify GlobalDispatchCoordinator is exported from domain.__init__."""
    from vibe3.domain import GlobalDispatchCoordinator

    assert GlobalDispatchCoordinator is not None
