"""Tests for collect_label_anomalies function."""

from vibe3.clients import collect_label_anomalies


class TestCollectLabelAnomalies:
    """Tests for collect_label_anomalies function."""

    def test_no_anomalies(self) -> None:
        result = collect_label_anomalies(
            ["state/ready"], issue_number=1, has_local_flow=True, is_manager_issue=False
        )
        assert result == []

    def test_roadmap_conflict(self) -> None:
        result = collect_label_anomalies(
            ["roadmap/rfc", "state/claimed"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert len(result) == 1
        assert "roadmap_conflict" in result[0].rule
        assert "state/claimed" in result[0].removed

    def test_multi_state_no_roadmap(self) -> None:
        result = collect_label_anomalies(
            ["state/review", "state/blocked"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=False,
        )
        assert len(result) == 1
        assert "multi_state" in result[0].rule
        assert result[0].removed == ["state/review"]

    def test_orphan_execution_state(self) -> None:
        result = collect_label_anomalies(
            ["state/in-progress"],
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
        )
        assert len(result) == 1
        assert "orphan_execution" in result[0].rule
        assert "state/in-progress" in result[0].removed
        assert "state/ready" in result[0].added

    def test_orphan_execution_skipped_when_has_flow(self) -> None:
        result = collect_label_anomalies(
            ["state/in-progress"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert result == []

    def test_governed_without_terminal_label_backfills_ready(self) -> None:
        result = collect_label_anomalies(
            ["orchestra-governed"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert len(result) == 1
        assert "governed_missing_state" in result[0].rule
        assert result[0].removed == []
        assert result[0].added == ["state/ready"]

    def test_governed_missing_state_skipped_when_has_state(self) -> None:
        result = collect_label_anomalies(
            ["orchestra-governed", "state/ready"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert result == []

    def test_governed_missing_state_skipped_when_rfc_or_epic(self) -> None:
        for roadmap_label in ("roadmap/rfc", "roadmap/epic"):
            result = collect_label_anomalies(
                ["orchestra-governed", roadmap_label],
                issue_number=1,
                has_local_flow=True,
                is_manager_issue=True,
            )
            assert result == []

    def test_roadmap_skips_multi_state_rule(self) -> None:
        result = collect_label_anomalies(
            ["roadmap/epic", "state/blocked", "state/review"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        rules = [a.rule for a in result]
        assert "multi_state" not in rules

    def test_governed_missing_state_non_manager_issue(self) -> None:
        """governed_missing_state fires even for non-manager issues."""
        result = collect_label_anomalies(
            ["orchestra-governed"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=False,  # non-manager
        )
        assert len(result) == 1
        assert "governed_missing_state" in result[0].rule
        assert result[0].added == ["state/ready"]

    def test_governed_missing_state_skipped_on_roadmap_non_manager(self) -> None:
        """roadmap labels still suppress governed_missing_state rule for non-manager."""
        for roadmap_label in ("roadmap/rfc", "roadmap/epic"):
            result = collect_label_anomalies(
                ["orchestra-governed", roadmap_label],
                issue_number=1,
                has_local_flow=True,
                is_manager_issue=False,
            )
            assert result == []
