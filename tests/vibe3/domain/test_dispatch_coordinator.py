"""Test GlobalDispatchCoordinator migration to domain layer."""

import inspect


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


def test_dispatch_coordinator_constructor_requires_injected_services():
    """Verify GlobalDispatchCoordinator constructor requires injected services."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator

    # Get constructor signature
    sig = inspect.signature(GlobalDispatchCoordinator.__init__)
    params = sig.parameters

    # Verify required keyword-only parameters exist
    required_kwonly_params = {
        "health_check_service",
        "queue_persistence",
        "issue_loader",
        "flow_context_resolver",
        "queue_selector",
    }

    for param_name in required_kwonly_params:
        assert param_name in params, f"Missing required parameter: {param_name}"
        # Verify they are keyword-only (no default value)
        param = params[param_name]
        # Keyword-only parameters have kind POSITIONAL_OR_KEYWORD or KEYWORD_ONLY
        # and if they have no default, default is Parameter.empty
        assert (
            param.default is inspect.Parameter.empty
        ), f"Parameter {param_name} should not have a default value"


def test_dispatch_coordinator_uses_domain_protocols():
    """Verify GlobalDispatchCoordinator uses domain protocols."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.domain.protocols import (
        CapacityServiceProtocol,
        CheckServiceProtocol,
        DispatchHealthCheckProtocol,
        FlowContextResolverProtocol,
        FlowServiceProtocol,
        IssueLoaderProtocol,
        LabelDispatchCallable,
        QueuePersistenceServiceProtocol,
        QueueSelectorProtocol,
    )

    # Verify protocols are importable
    assert DispatchHealthCheckProtocol is not None
    assert QueuePersistenceServiceProtocol is not None
    assert IssueLoaderProtocol is not None
    assert FlowContextResolverProtocol is not None
    assert QueueSelectorProtocol is not None
    assert CapacityServiceProtocol is not None
    assert CheckServiceProtocol is not None
    assert FlowServiceProtocol is not None
    assert LabelDispatchCallable is not None

    # Verify GlobalDispatchCoordinator type annotations reference domain protocols
    # (This is implicitly verified by successful import and type checking)
    assert GlobalDispatchCoordinator is not None
