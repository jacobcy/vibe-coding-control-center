"""Session role type definitions."""

from typing import Literal

SessionRole = Literal[
    "manager", "planner", "executor", "reviewer", "supervisor", "governance"
]
