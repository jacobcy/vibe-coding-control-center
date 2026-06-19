"""Runtime layer protocol interfaces.

Re-exported from runtime.protocols (KERNEL layer) to maintain backward compatibility
for domain consumers. The canonical definitions live in runtime/protocols.py
to break KERNEL→OBSERVATION dependency violations.
"""

from vibe3.runtime import ServiceBase  # re-export from runtime

__all__ = ["ServiceBase"]
