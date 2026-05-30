"""Test orchestra/global_dispatch_coordinator adapter shell."""


def test_global_dispatch_coordinator_reexports_from_domain():
    """Verify orchestra re-exports GlobalDispatchCoordinator from domain."""
    from vibe3.domain.dispatch_coordinator import (
        GlobalDispatchCoordinator as DomainCoordinator,
    )
    from vibe3.orchestra.global_dispatch_coordinator import GlobalDispatchCoordinator

    assert GlobalDispatchCoordinator is DomainCoordinator
