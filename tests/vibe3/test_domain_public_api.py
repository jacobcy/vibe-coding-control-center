"""Tests for public API exports used by domain module."""


def test_models_allowed_forbidden_transitions_importable() -> None:
    """Test ALLOWED_TRANSITIONS and FORBIDDEN_TRANSITIONS are importable."""
    from vibe3.models import ALLOWED_TRANSITIONS, FORBIDDEN_TRANSITIONS

    assert ALLOWED_TRANSITIONS is not None
    assert FORBIDDEN_TRANSITIONS is not None
    assert isinstance(ALLOWED_TRANSITIONS, set)
    assert isinstance(FORBIDDEN_TRANSITIONS, set)


def test_models_all_contains_transition_constants() -> None:
    """Test that __all__ contains transition constants."""
    from vibe3.models import __all__

    assert "ALLOWED_TRANSITIONS" in __all__
    assert "FORBIDDEN_TRANSITIONS" in __all__


def test_services_blocked_state_service_importable() -> None:
    """Test that BlockedStateService is importable from services."""
    from vibe3.services.flow import BlockedStateService

    assert BlockedStateService is not None


def test_services_flow_cleanup_service_importable() -> None:
    """Test that FlowCleanupService is importable from services."""
    from vibe3.services.flow import FlowCleanupService

    assert FlowCleanupService is not None


def test_services_task_resume_operations_importable() -> None:
    """Test that TaskResumeOperations is importable from services."""
    from vibe3.services.task import TaskResumeOperations

    assert TaskResumeOperations is not None


def test_services_error_helpers_importable() -> None:
    """Test that error helper functions are importable from services."""
    from vibe3.services.orchestra import record_error
    from vibe3.services.shared import has_recent_specific_error

    assert callable(has_recent_specific_error)
    assert callable(record_error)


def test_services_all_contains_new_symbols() -> None:
    """Test that __all__ contains newly exported symbols."""
    import vibe3.services

    root_barrel_all = vibe3.services.__all__

    assert "BlockedStateService" in root_barrel_all
    assert "FlowCleanupService" in root_barrel_all
    assert "TaskResumeOperations" in root_barrel_all
    assert "has_recent_specific_error" in root_barrel_all
    assert "record_error" in root_barrel_all


def test_execution_resolve_async_cli_project_root_importable() -> None:
    """Test that resolve_async_cli_project_root is importable from execution."""
    from vibe3.execution import resolve_async_cli_project_root

    assert callable(resolve_async_cli_project_root)


def test_execution_all_contains_new_symbol() -> None:
    """Test that __all__ contains newly exported symbol."""
    from vibe3.execution import __all__

    assert "resolve_async_cli_project_root" in __all__
