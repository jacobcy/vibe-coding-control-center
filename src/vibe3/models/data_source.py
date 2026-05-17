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
        ORCHESTRA_SERVER: Data from Orchestra HTTP server snapshot
    """

    LOCAL_SQLITE = "local"
    GITHUB_API = "github"
    ISSUE_BODY_FALLBACK = "fallback"
    ORCHESTRA_SERVER = "server"
