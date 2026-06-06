"""Protocol definitions for clients.

This package consolidates all Protocol definitions under clients.protocols.
All symbols are re-exported for backward compatibility.

Import paths:
    # Recommended (explicit source)
    from vibe3.clients.protocols.github import GitHubClientProtocol
    from vibe3.clients.protocols.backend import BackendProtocol

    # Backward compatible (package re-export)
    from vibe3.clients.protocols import GitHubClientProtocol, BackendProtocol
"""

from vibe3.clients.protocols.backend import BackendProtocol
from vibe3.clients.protocols.flow import FlowReader
from vibe3.clients.protocols.git import GitPathProtocol
from vibe3.clients.protocols.github import (
    GitHubAuthPort,
    GitHubClientProtocol,
    IssueReadPort,
    IssueWritePort,
    PRCommentPort,
    PRDiffPort,
    PRReadPort,
    PRWritePort,
)
from vibe3.clients.protocols.pr import BaseResolver
from vibe3.clients.protocols.role import TriggerableRoleDefinitionProtocol

__all__ = [
    "BackendProtocol",
    "FlowReader",
    "GitPathProtocol",
    "GitHubAuthPort",
    "GitHubClientProtocol",
    "IssueReadPort",
    "IssueWritePort",
    "PRCommentPort",
    "PRDiffPort",
    "PRReadPort",
    "PRWritePort",
    "BaseResolver",
    "TriggerableRoleDefinitionProtocol",
]
