"""Re-export shim for issue dispatch policy.

The actual implementation has moved to
vibe3.services.issue.dispatch_policy.
"""

from vibe3.services.issue.dispatch_policy import DispatchExclusion, IssueDispatchPolicy

__all__ = ["DispatchExclusion", "IssueDispatchPolicy"]
