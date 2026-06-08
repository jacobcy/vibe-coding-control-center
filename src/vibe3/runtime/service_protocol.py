"""Service protocol for runtime observers.

Re-exports ServiceBase from domain/protocols to maintain backward compatibility.
Actual definition moved to domain/protocols/runtime_protocols.py to break
the domain→runtime circular dependency.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.domain import ServiceBase


def __getattr__(name: str) -> object:
    if name == "ServiceBase":
        from vibe3.domain import ServiceBase

        return ServiceBase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ServiceBase"]
