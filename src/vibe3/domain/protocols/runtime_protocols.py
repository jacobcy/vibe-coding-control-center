"""Runtime layer protocol interfaces.

Re-exported from orchestra (KERNEL layer) to maintain backward compatibility
for domain consumers. The canonical definitions live in orchestra/domain_types.py
to break KERNEL→OBSERVATION dependency violations.
"""

from vibe3.orchestra import ServiceBase  # re-export from KERNEL

__all__ = ["ServiceBase"]
