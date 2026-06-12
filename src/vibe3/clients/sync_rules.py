"""Sync rules configuration for remote/local label alignment.

This module provides fine-grained control over which sync/alignment rules
are active during remote label checks (orchestra dispatch) and local flow
consistency checks (vibe3 check).

Architecture:
- Remote rules: Applied by orchestra during periodic GitHub issue label scans
- Local rules: Applied by CheckService during flow consistency verification

Default behavior: All rules enabled (backward compatible with pre-config behavior).

Configuration path: config/v3/sync_rules.yaml
Registry entry: config/v3/registry.yaml (sync_rules governance)

Rule Categories:
- Remote rules (4): Handle remote label anomalies detected by orchestra
  - roadmap_conflict: Remove state labels when roadmap/rfc or roadmap/epic present
  - multi_state: Keep only highest-priority state label
  - orphan_execution: Reset execution state to state/ready when no local flow
  - governed_missing_state: Add state/ready to orchestra-governed issues missing state

- Local rules (10): Handle local flow consistency during vibe3 check
  - multi_state_label_fix: Auto-correct multiple state labels to highest priority
  - pr_terminal_state: Handle PR merged/closed → mark flow aborted
  - closed_issue_sync: Handle closed task issue → mark flow aborted
  - stale_blocked_sync: Auto-resume flow when remote state/blocked label removed
  - stale_ready_rebuild: Rebuild stale ready flow from remote issue state
  - missing_branch_cleanup: Mark flow aborted when local branch deleted
  - orphaned_flow_cleanup: Mark orphaned active flows (>100 commits behind) as aborted
  - empty_ready_cleanup: Mark empty ready flows as stale
  - flow_consistency_recovery: Auto-recover inconsistent flow state
  - missing_state_label_recovery: Recover missing remote state label from local flow
"""

from pydantic import BaseModel, Field


class SyncRule(BaseModel):
    """Individual sync rule configuration."""

    enabled: bool = True
    description: str = ""


class RemoteSyncRules(BaseModel):
    """Remote domain sync rules (label anomaly detection)."""

    roadmap_conflict: SyncRule = Field(
        default_factory=SyncRule,
        description="Remove state labels when roadmap/rfc or roadmap/epic present",
    )
    multi_state: SyncRule = Field(
        default_factory=SyncRule,
        description="Keep only highest-priority state label",
    )
    orphan_execution: SyncRule = Field(
        default_factory=SyncRule,
        description="Reset execution state to state/ready when no local flow",
    )
    governed_missing_state: SyncRule = Field(
        default_factory=SyncRule,
        description="Add state/ready to orchestra-governed issues missing state",
    )


class LocalSyncRules(BaseModel):
    """Local domain sync rules (flow alignment checks)."""

    multi_state_label_fix: SyncRule = Field(
        default_factory=SyncRule,
        description=(
            "Fix multiple state labels on issue " "(auto-correct to highest priority)"
        ),
    )
    pr_terminal_state: SyncRule = Field(
        default_factory=SyncRule,
        description="Handle PR merged/closed → mark flow aborted",
    )
    closed_issue_sync: SyncRule = Field(
        default_factory=SyncRule,
        description="Handle closed task issue → mark flow aborted",
    )
    stale_blocked_sync: SyncRule = Field(
        default_factory=SyncRule,
        description="Auto-resume flow when remote state/blocked label removed",
    )
    stale_ready_rebuild: SyncRule = Field(
        default_factory=SyncRule,
        description="Rebuild stale ready flow from remote issue state",
    )
    missing_branch_cleanup: SyncRule = Field(
        default_factory=SyncRule,
        description="Mark flow aborted when local branch deleted",
    )
    orphaned_flow_cleanup: SyncRule = Field(
        default_factory=SyncRule,
        description="Mark orphaned active flows (>100 commits behind) as aborted",
    )
    empty_ready_cleanup: SyncRule = Field(
        default_factory=SyncRule,
        description="Mark empty ready flows as stale",
    )
    flow_consistency_recovery: SyncRule = Field(
        default_factory=SyncRule,
        description="Auto-recover inconsistent flow state",
    )
    missing_state_label_recovery: SyncRule = Field(
        default_factory=SyncRule,
        description="Recover missing remote state label from local flow",
    )


class SyncRulesConfig(BaseModel):
    """Complete sync rules configuration."""

    remote: RemoteSyncRules = Field(
        default_factory=RemoteSyncRules, description="Remote domain rules"
    )
    local: LocalSyncRules = Field(
        default_factory=LocalSyncRules, description="Local domain rules"
    )


def load_sync_rules(config_path: str = "config/v3/sync_rules.yaml") -> SyncRulesConfig:
    """Load sync rules from YAML config file.

    Args:
        config_path: Path to sync rules config file

    Returns:
        SyncRulesConfig instance (defaults to all enabled if file not found)
    """
    import logging
    from pathlib import Path

    import yaml
    from pydantic import ValidationError

    logger = logging.getLogger(__name__)

    path = Path(config_path)
    if not path.exists():
        logger.info(f"Sync rules config not found at {config_path}, using defaults")
        return SyncRulesConfig()

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return SyncRulesConfig(**data)
    except ValidationError as e:
        logger.warning(
            f"Invalid sync rules config at {config_path}, using defaults: {e}"
        )
        return SyncRulesConfig()
    except Exception as e:
        logger.warning(
            f"Failed to load sync rules config from {config_path}, using defaults: {e}"
        )
        return SyncRulesConfig()
