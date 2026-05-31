"""Adapter shell for backward compatibility.

.. deprecated:: 3.0.0
    Use vibe3.domain.FailedGate instead.
    This module will be removed in a future version.
"""

import warnings

from vibe3.domain import FailedGate
from vibe3.orchestra import GateResult, GateStatus

# Emit deprecation warning when module is imported
warnings.warn(
    "Importing FailedGate from orchestra.failed_gate is deprecated. "
    "Use 'from vibe3.domain import FailedGate' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["FailedGate", "GateResult", "GateStatus"]
