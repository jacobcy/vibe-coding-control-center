"""Dispatch-related data models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchExclusion:
    """Structured reason why an issue should not be auto-dispatched."""

    code: str
    message: str
