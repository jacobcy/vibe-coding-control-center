"""DataSource provenance tracking enum.

Tracks where flow/status/task data originated for source-aware reads.
"""

from enum import Enum


class DataSource(str, Enum):
    """Data source provenance for flow/status reads.

    Attributes:
        LOCAL_SQLITE: Data from local SQLite flow_state table
        GITHUB_API: Data from GitHub PR/issue API
        ISSUE_BODY_FALLBACK: Data from issue body managed section projection
    """

    LOCAL_SQLITE = "local"
    GITHUB_API = "github"
    ISSUE_BODY_FALLBACK = "fallback"
