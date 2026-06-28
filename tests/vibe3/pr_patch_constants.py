"""Shared patch-path constants for PR service subpackage tests.

When PR service modules are reorganized, update the constants here —
tests that reference these constants will not need individual changes.
"""

# Subpackage module paths — use these to compose full patch targets
PR_CREATE = "vibe3.services.pr.create"
PR_SERVICE = "vibe3.services.pr.service"
PR_BASE_RESOLUTION = "vibe3.services.pr.base_resolution"
PR_RESOLVER = "vibe3.services.pr.resolver"
PR_VERDICT_SERVICE = "vibe3.services.pr.verdict_service"
PR_UTILS = "vibe3.services.pr.utils"

# Package-level path for public API symbols (preferred when symbol is in __all__)
PR_PACKAGE = "vibe3.services.pr"
