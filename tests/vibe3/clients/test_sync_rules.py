"""Tests for sync rules configuration."""

import tempfile
from pathlib import Path

from vibe3.clients import RemoteSyncRules, SyncRule, SyncRulesConfig, load_sync_rules


class TestSyncRulesModel:
    """Test SyncRulesConfig model."""

    def test_default_all_enabled(self):
        """Default SyncRulesConfig has all rules enabled."""
        config = SyncRulesConfig()

        # Remote rules
        assert config.remote.roadmap_conflict.enabled is True
        assert config.remote.multi_state.enabled is True
        assert config.remote.orphan_execution.enabled is True
        assert config.remote.governed_missing_state.enabled is True

        # Local rules
        assert config.local.multi_state_label_fix.enabled is True
        assert config.local.pr_terminal_state.enabled is True
        assert config.local.closed_issue_sync.enabled is True
        assert config.local.stale_blocked_sync.enabled is True
        assert config.local.stale_ready_rebuild.enabled is True
        assert config.local.missing_branch_cleanup.enabled is True
        assert config.local.orphaned_flow_cleanup.enabled is True
        assert config.local.empty_ready_cleanup.enabled is True
        assert config.local.flow_consistency_recovery.enabled is True
        assert config.local.missing_state_label_recovery.enabled is True

    def test_partial_override(self):
        """Disabling one rule only affects that rule."""
        config = SyncRulesConfig(
            remote=RemoteSyncRules(roadmap_conflict=SyncRule(enabled=False))
        )

        assert config.remote.roadmap_conflict.enabled is False
        assert config.remote.multi_state.enabled is True  # Still enabled

    def test_load_from_yaml(self):
        """Loading from a real YAML file works."""
        config = load_sync_rules("config/v3/sync_rules.yaml")

        assert isinstance(config, SyncRulesConfig)
        assert config.remote.roadmap_conflict.enabled is True
        assert config.local.multi_state_label_fix.enabled is True

    def test_missing_file_returns_defaults(self):
        """When YAML file doesn't exist, defaults apply."""
        config = load_sync_rules("config/v3/nonexistent.yaml")

        assert isinstance(config, SyncRulesConfig)
        assert config.remote.roadmap_conflict.enabled is True
        assert config.local.multi_state_label_fix.enabled is True

    def test_all_disabled_no_anomalies(self):
        """When all remote rules disabled, no anomalies detected."""
        from vibe3.services.shared.label_anomalies import collect_label_anomalies

        config = SyncRulesConfig(
            remote=RemoteSyncRules(
                roadmap_conflict=SyncRule(enabled=False),
                multi_state=SyncRule(enabled=False),
                orphan_execution=SyncRule(enabled=False),
                governed_missing_state=SyncRule(enabled=False),
            )
        )

        labels = ["state/blocked", "state/in-progress", "roadmap/rfc"]
        anomalies = collect_label_anomalies(
            labels,
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
            rules=config,
        )

        assert len(anomalies) == 0

    def test_malformed_yaml_returns_defaults(self):
        """Malformed YAML content returns default config."""
        # Create a temp file with malformed YAML
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid yaml content:\n  - [unclosed\n  brackets")
            temp_path = f.name

        try:
            config = load_sync_rules(temp_path)

            # Should return default config (all enabled)
            assert isinstance(config, SyncRulesConfig)
            assert config.remote.roadmap_conflict.enabled is True
            assert config.local.multi_state_label_fix.enabled is True
        finally:
            Path(temp_path).unlink()
