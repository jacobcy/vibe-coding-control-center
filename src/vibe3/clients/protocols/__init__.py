"""Protocol definitions for clients.

This package consolidates all Protocol definitions under clients.protocols.
All symbols are re-exported for backward compatibility.
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
]
