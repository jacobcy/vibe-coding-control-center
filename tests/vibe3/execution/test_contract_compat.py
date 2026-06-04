"""Backward compatibility tests for execution contract import paths."""


def test_execution_contracts_reexport_moved_contracts() -> None:
    """Legacy execution.contracts imports should resolve to canonical models."""
    from vibe3.execution.contracts import (
        ExecutionLaunchResult,
        ExecutionRequest,
        WorktreeRequirement,
    )
    from vibe3.models.execution_request import (
        ExecutionLaunchResult as ModelExecutionLaunchResult,
    )
    from vibe3.models.execution_request import ExecutionRequest as ModelExecutionRequest
    from vibe3.models.worktree import WorktreeRequirement as ModelWorktreeRequirement

    assert ExecutionRequest is ModelExecutionRequest
    assert ExecutionLaunchResult is ModelExecutionLaunchResult
    assert WorktreeRequirement is ModelWorktreeRequirement


def test_execution_session_service_reexports_session_role() -> None:
    """Legacy session_service SessionRole import should remain available."""
    from vibe3.execution.session_service import SessionRole
    from vibe3.models.session_types import SessionRole as ModelSessionRole

    assert SessionRole is ModelSessionRole
