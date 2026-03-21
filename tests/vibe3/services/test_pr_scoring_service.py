"""PRScoringService 单元测试."""

from vibe3.services.pr_scoring_service import (
    PRDimensions,
    RiskLevel,
    calculate_risk_score,
    determine_risk_level,
    generate_score_report,
)


class TestDetermineRiskLevel:
    """determine_risk_level 阈值测试."""

    def test_low_risk(self) -> None:
        assert determine_risk_level(0) == RiskLevel.LOW
        assert determine_risk_level(2) == RiskLevel.LOW

    def test_medium_risk(self) -> None:
        assert determine_risk_level(3) == RiskLevel.MEDIUM
        assert determine_risk_level(5) == RiskLevel.MEDIUM

    def test_high_risk(self) -> None:
        assert determine_risk_level(6) == RiskLevel.HIGH
        assert determine_risk_level(8) == RiskLevel.HIGH

    def test_critical_risk(self) -> None:
        assert determine_risk_level(9) == RiskLevel.CRITICAL
        assert determine_risk_level(15) == RiskLevel.CRITICAL


class TestCalculateRiskScore:
    """calculate_risk_score 评分逻辑测试."""

    def test_zero_score_for_minimal_pr(self) -> None:
        dims = PRDimensions(changed_lines=10, changed_files=1, impacted_modules=1)
        result = calculate_risk_score(dims)
        assert result.score == 0
        assert result.level == RiskLevel.LOW
        assert result.block is False

    def test_large_pr_scores_higher(self) -> None:
        dims = PRDimensions(changed_lines=600, changed_files=15, impacted_modules=6)
        result = calculate_risk_score(dims)
        assert result.score >= 5

    def test_critical_path_adds_weight(self) -> None:
        base = PRDimensions(changed_lines=10, changed_files=1)
        with_critical = PRDimensions(
            changed_lines=10, changed_files=1, critical_path_touch=True
        )
        base_score = calculate_risk_score(base).score
        critical_score = calculate_risk_score(with_critical).score
        assert critical_score > base_score

    def test_codex_critical_verdict_adds_weight(self) -> None:
        # codex_verdict="CRITICAL" adds weight 5
        # block determined by score >= 9 or verdict in block_on_verdict
        dims = PRDimensions(changed_lines=10, codex_verdict="CRITICAL")
        result = calculate_risk_score(dims)
        assert result.breakdown.get("codex_critical", 0) == 5

    def test_block_verdict_blocks(self) -> None:
        # block_on_verdict 配置为 ["BLOCK"]
        dims = PRDimensions(changed_lines=10, codex_verdict="BLOCK")
        result = calculate_risk_score(dims)
        assert result.block is True

    def test_codex_major_adds_weight(self) -> None:
        base = PRDimensions(changed_lines=10)
        with_major = PRDimensions(changed_lines=10, codex_verdict="MAJOR")
        assert calculate_risk_score(with_major).score > calculate_risk_score(base).score

    def test_breakdown_keys_present(self) -> None:
        dims = PRDimensions(
            changed_lines=300,
            changed_files=5,
            impacted_modules=3,
            critical_path_touch=True,
        )
        result = calculate_risk_score(dims)
        assert "changed_lines" in result.breakdown
        assert "changed_files" in result.breakdown
        assert "critical_path_touch" in result.breakdown


class TestGenerateScoreReport:
    """generate_score_report 输出格式测试."""

    def test_report_contains_required_keys(self) -> None:
        dims = PRDimensions(changed_lines=100, changed_files=3)
        report = generate_score_report(dims)
        assert "score" in report
        assert "level" in report
        assert "block" in report
        assert "breakdown" in report
        assert "dimensions" in report
        assert "reason" in report
        assert "trigger_factors" in report
        assert "recommendations" in report

    def test_report_explains_blocking_risk(self) -> None:
        dims = PRDimensions(
            changed_lines=600,
            changed_files=12,
            impacted_modules=6,
            critical_path_touch=True,
            public_api_touch=True,
        )
        report = generate_score_report(dims)

        assert report["block"] is True
        assert report["reason"] != "未知"
        assert len(report["trigger_factors"]) > 0
        assert any("降低" in item or "拆分" in item for item in report["recommendations"])
