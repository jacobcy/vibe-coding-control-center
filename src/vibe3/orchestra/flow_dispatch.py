"""Adapter shell for backward compatibility.

.. deprecated:: 3.0.0
    Use vibe3.domain.FlowManager instead.
    This module will be removed in a future version.
"""

import warnings

from vibe3.domain import FlowManager

# Emit deprecation warning when module is imported
warnings.warn(
    "Importing FlowManager from orchestra.flow_dispatch is deprecated. "
    "Use 'from vibe3.domain import FlowManager' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["FlowManager"]
