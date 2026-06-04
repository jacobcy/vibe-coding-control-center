"""Infrastructure layer protocol interfaces to break circular dependencies."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConfigLoaderProtocol(Protocol):
    """Protocol for config loading to break utils → config dependency."""

    def load_orchestra_config(self) -> dict[str, Any]:
        """Load orchestra configuration."""
        ...

    def get_manager_usernames(self) -> list[str]:
        """Get manager usernames from config."""
        ...


@runtime_checkable
class GitClientProtocol(Protocol):
    """Protocol for git operations to break config → clients dependency."""

    def find_repo_root(self) -> str | None:
        """Find repository root directory."""
        ...

    def get_current_branch(self) -> str:
        """Get current git branch name."""
        ...


@runtime_checkable
class ExceptionFactoryProtocol(Protocol):
    """Protocol for exception creation to break utils → exceptions dependency."""

    def create_git_error(self, message: str) -> Exception:
        """Create a GitError exception."""
        ...

    def create_config_error(self, message: str) -> Exception:
        """Create a ConfigError exception."""
        ...
