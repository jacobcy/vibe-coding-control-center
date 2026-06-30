"""Tests for label anomaly rules with sync rules."""

from vibe3.clients import (
    RemoteSyncRules,
    SyncRule,
    SyncRulesConfig,
    collect_label_anomalies,
)


class TestLabelAnomaliesSyncRules:
    """Test collect_label_anomalies with sync rules."""

    def test_remote_rule_disabled(self):
        """Disabling roadmap_conflict skips only that rule."""
        config = SyncRulesConfig(
            remote=RemoteSyncRules(roadmap_conflict=SyncRule(enabled=False))
        )

        # Labels have roadmap/rfc + state labels, which would trigger roadmap_conflict
        labels = ["roadmap/rfc", "state/blocked", "state/in-progress"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
            rules=config,
        )

        # roadmap_conflict disabled, so multi_state rule should apply
        assert len(anomalies) == 1
        assert "multi_state" in anomalies[0].rule
        assert "roadmap_conflict" not in anomalies[0].rule

    def test_all_remote_rules_enabled_default(self):
        """Default config = current behavior (all rules enabled)."""
        config = SyncRulesConfig()
        labels = ["roadmap/rfc", "state/blocked"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
            rules=config,
        )

        assert len(anomalies) == 1
        assert "roadmap_conflict" in anomalies[0].rule
        assert anomalies[0].removed == ["state/blocked"]

    def test_partial_disable(self):
        """Disabling multi_state + orphan_execution works independently."""
        config = SyncRulesConfig(
            remote=RemoteSyncRules(
                multi_state=SyncRule(enabled=False),
                orphan_execution=SyncRule(enabled=False),
            )
        )

        # Multiple state labels
        labels = ["state/blocked", "state/in-progress"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
            rules=config,
        )

        # multi_state disabled, so no anomalies
        assert len(anomalies) == 0

    def test_governed_missing_state_disabled(self):
        """Disabling governed_missing_state skips that rule."""
        config = SyncRulesConfig(
            remote=RemoteSyncRules(governed_missing_state=SyncRule(enabled=False))
        )

        # Orchestra-governed issue with no state label
        labels = ["orchestra-governed"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
            rules=config,
        )

        assert len(anomalies) == 0

    def test_none_rules_all_enabled(self):
        """Passing None for rules means all rules enabled (backward compatible)."""
        labels = ["roadmap/rfc", "state/blocked"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
            rules=None,  # Backward compatible
        )

        assert len(anomalies) == 1
        assert "roadmap_conflict" in anomalies[0].rule

    # ---- Supervisor label protection regression (#3208) ----

    def test_supervisor_multi_state_not_removed(self):
        """Supervisor issues with multiple state labels skip multi_state rule.

        Supervisor issues independently manage their own state labels (e.g.,
        state/handoff) and must not have them stripped by label normalization.
        Regression test for #3208.
        """
        labels = ["supervisor", "state/blocked", "state/handoff"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=3160,
            has_local_flow=False,
            is_manager_issue=False,
        )

        # multi_state must NOT trigger for supervisor issues
        multi_state = [a for a in anomalies if "multi_state" in a.rule]
        assert (
            not multi_state
        ), f"multi_state triggered for supervisor issue: {multi_state}"

    def test_non_supervisor_multi_state_still_triggers(self):
        """Non-supervisor issues with multiple state labels trigger multi_state."""
        labels = ["bug", "state/blocked", "state/handoff"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=9999,
            has_local_flow=False,
            is_manager_issue=False,
        )

        # multi_state SHOULD trigger for non-supervisor issues
        multi_state = [a for a in anomalies if "multi_state" in a.rule]
        assert multi_state, "multi_state should trigger for non-supervisor issues"
        # handoff has lower priority, should be removed
        assert "state/handoff" in multi_state[0].removed
        # blocked has highest priority, should be kept
        assert "state/blocked" not in multi_state[0].removed

    def test_supervisor_with_single_state_no_anomaly(self):
        """Supervisor issue with a single state label produces no anomalies."""
        labels = ["supervisor", "state/handoff"]

        anomalies = collect_label_anomalies(
            labels,
            issue_number=3160,
            has_local_flow=False,
            is_manager_issue=False,
        )

        assert (
            len(anomalies) == 0
        ), f"Expected no anomalies for single-state supervisor issue, got: {anomalies}"
