"""Label anomaly detection for issue audit.

Extracted from labels.py to keep that module focused on predicates.
"""

from __future__ import annotations

from vibe3.clients import LabelAnomaly, collect_label_anomalies

# Re-export for backward compatibility
__all__ = ["LabelAnomaly", "collect_label_anomalies"]
