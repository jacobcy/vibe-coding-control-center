"""Service protocol for runtime observers.

Re-exports ServiceBase from domain/protocols to maintain backward compatibility.
Actual definition moved to domain/protocols/runtime_protocols.py to break
the domain→runtime circular dependency.
"""

from vibe3.domain.protocols.runtime_protocols import ServiceBase

__all__ = ["ServiceBase"]
