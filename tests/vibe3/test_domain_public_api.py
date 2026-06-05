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
    from vibe3.services import BlockedStateService

    assert BlockedStateService is not None


def test_services_flow_cleanup_service_importable() -> None:
    """Test that FlowCleanupService is importable from services."""
    from vibe3.services import FlowCleanupService

    assert FlowCleanupService is not None


def test_services_task_resume_operations_importable() -> None:
    """Test that TaskResumeOperations is importable from services."""
    from vibe3.services import TaskResumeOperations

    assert TaskResumeOperations is not None


def test_services_error_helpers_importable() -> None:
    """Test that error helper functions are importable from services."""
    from vibe3.services import has_recent_specific_error, record_error

    assert callable(has_recent_specific_error)
    assert callable(record_error)


def test_services_all_contains_new_symbols() -> None:
    """Test that __all__ contains newly exported symbols."""
    from vibe3.services import __all__

    assert "BlockedStateService" in __all__
    assert "FlowCleanupService" in __all__
    assert "TaskResumeOperations" in __all__
    assert "has_recent_specific_error" in __all__
    assert "record_error" in __all__


def test_execution_resolve_async_cli_project_root_importable() -> None:
    """Test that resolve_async_cli_project_root is importable from execution."""
    from vibe3.execution import resolve_async_cli_project_root

    assert callable(resolve_async_cli_project_root)


def test_execution_all_contains_new_symbol() -> None:
    """Test that __all__ contains newly exported symbol."""
    from vibe3.execution import __all__

    assert "resolve_async_cli_project_root" in __all__
