"""Test imports for deprecated code migration."""


def test_orchestra_imports_use_new_paths():
    """Test that orchestra imports work from new locations."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.domain.failed_gate import FailedGate
    from vibe3.domain.flow_manager import FlowManager
    from vibe3.orchestra.protocols import FlowManagerProtocol

    # Verify classes are imported correctly
    assert FailedGate is not None
    assert FlowManager is not None
    assert GlobalDispatchCoordinator is not None
    assert FlowManagerProtocol is not None

    # Verify they are the correct classes
    assert FailedGate.__name__ == "FailedGate"
    assert FlowManager.__name__ == "FlowManager"
    assert GlobalDispatchCoordinator.__name__ == "GlobalDispatchCoordinator"
    assert FlowManagerProtocol.__name__ == "FlowManagerProtocol"


def test_domain_module_exports():
    """Test that domain module properly exports orchestra components."""
    from vibe3 import domain

    # Test lazy imports through domain module
    assert domain.FailedGate is not None
    assert domain.FlowManager is not None
    assert domain.GlobalDispatchCoordinator is not None

    # Verify they are the correct classes
    assert domain.FailedGate.__name__ == "FailedGate"
    assert domain.FlowManager.__name__ == "FlowManager"
    assert domain.GlobalDispatchCoordinator.__name__ == "GlobalDispatchCoordinator"
