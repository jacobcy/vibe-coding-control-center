"""Protocol conformance tests for vibe3.clients.protocols.

Tests verify:
1. Importability of all exported symbols from explicit source modules
2. Each protocol is a typing.Protocol subclass and structural typing works
3. __all__ integrity matches public classes in each module
"""

import inspect
from typing import Protocol


class TestProtocolImports:
    """Test that every exported symbol is importable from its explicit source module."""

    def test_role_protocol_import(self) -> None:
        """Test TriggerableRoleDefinitionProtocol is importable from role.py."""
        from vibe3.clients.protocols.role import TriggerableRoleDefinitionProtocol

        assert TriggerableRoleDefinitionProtocol is not None

    def test_backend_protocol_import(self) -> None:
        """Test BackendProtocol is importable from backend.py."""
        from vibe3.clients.protocols.backend import BackendProtocol

        assert BackendProtocol is not None

    def test_flow_protocols_import(self) -> None:
        """Test FlowReader and FlowStatePort are importable from flow.py."""
        from vibe3.clients.protocols.flow import FlowReader, FlowStatePort

        assert FlowReader is not None
        assert FlowStatePort is not None

    def test_git_protocol_import(self) -> None:
        """Test GitPathProtocol is importable from git.py."""
        from vibe3.clients.protocols.git import GitPathProtocol

        assert GitPathProtocol is not None

    def test_github_protocols_import(self) -> None:
        """Test all GitHub protocols are importable from github.py."""
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

        assert GitHubAuthPort is not None
        assert PRReadPort is not None
        assert PRWritePort is not None
        assert PRDiffPort is not None
        assert PRCommentPort is not None
        assert IssueReadPort is not None
        assert IssueWritePort is not None
        assert GitHubClientProtocol is not None

    def test_pr_protocol_import(self) -> None:
        """Test BaseResolver is importable from pr.py."""
        from vibe3.clients.protocols.pr import BaseResolver

        assert BaseResolver is not None


class TestProtocolStructuralTyping:
    """Test each protocol is a typing.Protocol subclass and structural typing works."""

    def test_role_protocol_is_protocol(self) -> None:
        """Test TriggerableRoleDefinitionProtocol is a Protocol."""
        from vibe3.clients.protocols.role import TriggerableRoleDefinitionProtocol

        assert issubclass(TriggerableRoleDefinitionProtocol, Protocol)

    def test_backend_protocol_is_protocol(self) -> None:
        """Test BackendProtocol is a Protocol."""
        from vibe3.clients.protocols.backend import BackendProtocol

        assert issubclass(BackendProtocol, Protocol)

    def test_flow_reader_is_protocol(self) -> None:
        """Test FlowReader is a Protocol."""
        from vibe3.clients.protocols.flow import FlowReader

        assert issubclass(FlowReader, Protocol)

    def test_flow_state_port_is_protocol(self) -> None:
        """Test FlowStatePort is a Protocol."""
        from vibe3.clients.protocols.flow import FlowStatePort

        assert issubclass(FlowStatePort, Protocol)

    def test_git_path_protocol_is_protocol(self) -> None:
        """Test GitPathProtocol is a Protocol."""
        from vibe3.clients.protocols.git import GitPathProtocol

        assert issubclass(GitPathProtocol, Protocol)

    def test_github_auth_port_is_protocol(self) -> None:
        """Test GitHubAuthPort is a Protocol."""
        from vibe3.clients.protocols.github import GitHubAuthPort

        assert issubclass(GitHubAuthPort, Protocol)

    def test_pr_read_port_is_protocol(self) -> None:
        """Test PRReadPort is a Protocol."""
        from vibe3.clients.protocols.github import PRReadPort

        assert issubclass(PRReadPort, Protocol)

    def test_pr_write_port_is_protocol(self) -> None:
        """Test PRWritePort is a Protocol."""
        from vibe3.clients.protocols.github import PRWritePort

        assert issubclass(PRWritePort, Protocol)

    def test_pr_diff_port_is_protocol(self) -> None:
        """Test PRDiffPort is a Protocol."""
        from vibe3.clients.protocols.github import PRDiffPort

        assert issubclass(PRDiffPort, Protocol)

    def test_pr_comment_port_is_protocol(self) -> None:
        """Test PRCommentPort is a Protocol."""
        from vibe3.clients.protocols.github import PRCommentPort

        assert issubclass(PRCommentPort, Protocol)

    def test_issue_read_port_is_protocol(self) -> None:
        """Test IssueReadPort is a Protocol."""
        from vibe3.clients.protocols.github import IssueReadPort

        assert issubclass(IssueReadPort, Protocol)

    def test_issue_write_port_is_protocol(self) -> None:
        """Test IssueWritePort is a Protocol."""
        from vibe3.clients.protocols.github import IssueWritePort

        assert issubclass(IssueWritePort, Protocol)

    def test_github_client_protocol_is_protocol(self) -> None:
        """Test GitHubClientProtocol is a Protocol."""
        from vibe3.clients.protocols.github import GitHubClientProtocol

        assert issubclass(GitHubClientProtocol, Protocol)

    def test_base_resolver_is_protocol(self) -> None:
        """Test BaseResolver is a Protocol."""
        from vibe3.clients.protocols.pr import BaseResolver

        assert issubclass(BaseResolver, Protocol)


class TestProtocolAllIntegrity:
    """Test that __all__ matches the set of public classes defined in each module."""

    def test_role_module_all_integrity(self) -> None:
        """Test role.py __all__ matches public classes."""
        import vibe3.clients.protocols.role as role_module

        # Get all classes defined in the module
        public_classes = {
            name
            for name, obj in inspect.getmembers(role_module, inspect.isclass)
            if obj.__module__ == role_module.__name__ and not name.startswith("_")
        }

        assert set(role_module.__all__) == public_classes

    def test_backend_module_all_integrity(self) -> None:
        """Test backend.py __all__ matches public classes."""
        import vibe3.clients.protocols.backend as backend_module

        # Get all classes defined in the module
        public_classes = {
            name
            for name, obj in inspect.getmembers(backend_module, inspect.isclass)
            if obj.__module__ == backend_module.__name__ and not name.startswith("_")
        }

        assert set(backend_module.__all__) == public_classes

    def test_flow_module_all_integrity(self) -> None:
        """Test flow.py __all__ matches public classes."""
        import vibe3.clients.protocols.flow as flow_module

        # Get all classes defined in the module
        public_classes = {
            name
            for name, obj in inspect.getmembers(flow_module, inspect.isclass)
            if obj.__module__ == flow_module.__name__ and not name.startswith("_")
        }

        assert set(flow_module.__all__) == public_classes

    def test_git_module_all_integrity(self) -> None:
        """Test git.py __all__ matches public classes."""
        import vibe3.clients.protocols.git as git_module

        # Get all classes defined in the module
        public_classes = {
            name
            for name, obj in inspect.getmembers(git_module, inspect.isclass)
            if obj.__module__ == git_module.__name__ and not name.startswith("_")
        }

        assert set(git_module.__all__) == public_classes

    def test_github_module_all_integrity(self) -> None:
        """Test github.py __all__ matches public classes."""
        import vibe3.clients.protocols.github as github_module

        # Get all classes defined in the module
        public_classes = {
            name
            for name, obj in inspect.getmembers(github_module, inspect.isclass)
            if obj.__module__ == github_module.__name__ and not name.startswith("_")
        }

        assert set(github_module.__all__) == public_classes

    def test_pr_module_all_integrity(self) -> None:
        """Test pr.py __all__ matches public classes."""
        import vibe3.clients.protocols.pr as pr_module

        # Get all classes defined in the module
        public_classes = {
            name
            for name, obj in inspect.getmembers(pr_module, inspect.isclass)
            if obj.__module__ == pr_module.__name__ and not name.startswith("_")
        }

        assert set(pr_module.__all__) == public_classes
