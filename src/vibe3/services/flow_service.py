"""Flow service implementation."""

from typing import TYPE_CHECKING

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.config.settings import VibeConfig
from vibe3.services.flow_block_mixin import FlowLifecycleMixin
from vibe3.services.flow_transition import FlowTransitionMixin

if TYPE_CHECKING:
    pass


class FlowService(FlowLifecycleMixin, FlowTransitionMixin):
    """Service for managing flow state.

    Combines mixins for:
    - Lifecycle operations (block, abort) - from FlowLifecycleMixin
    - Read operations (get_flow_state, get_flow_status, list_flows, get_flow_timeline)
      - from FlowTransitionMixin → FlowReadMixin
    - Write operations (create_flow, update_flow_metadata, delete_flow, bind_spec)
      - from FlowTransitionMixin → FlowWriteMixin
    - Transition operations (ensure_flow_for_branch, reactivate_flow)
      - from FlowTransitionMixin
    """

    store: SQLiteClient
    git_client: GitClient
    config: VibeConfig

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        config: VibeConfig | None = None,
    ) -> None:
        """Initialize flow service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
            config: VibeConfig instance for configuration
        """
        self.store = SQLiteClient() if store is None else store
        self.git_client = GitClient() if git_client is None else git_client
        self.config = VibeConfig.get_defaults() if config is None else config

    def get_current_branch(self) -> str:
        """Get current git branch.

        Returns:
            Current branch name
        """
        return self.git_client.get_current_branch()
