"""Tests for GlobalDispatchCoordinator.

This test file has been refactored for LOC compliance.
All tests have been moved to focused modules:

- test_dispatch_queue_operations.py: Queue management tests (8 tests)
- test_dispatch_state_transitions.py: State transitions and logging tests (6 tests)

This file serves as a compatibility import point.
"""

from __future__ import annotations

# Tests have been moved to focused modules for LOC compliance
# Import tests from new modules for backward compatibility
from tests.vibe3.orchestra.test_dispatch_queue_operations import (  # noqa: F401
    TestQueueOperations,
)
from tests.vibe3.orchestra.test_dispatch_state_transitions import (  # noqa: F401
    TestLoggingBehavior,
    TestStateTransitions,
)

__all__ = [
    "TestQueueOperations",
    "TestStateTransitions",
    "TestLoggingBehavior",
]
