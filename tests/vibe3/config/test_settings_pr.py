"""Tests for PR scoring configuration models in settings_pr.py."""

from vibe3.config.settings_pr import (
    FileChangeWeights,
    LineChangeWeights,
    MergeGateConfig,
    ModuleChangeWeights,
    PRScoringConfig,
    PRScoringThresholds,
    PRScoringWeights,
    SizeThreshold,
    SizeThresholds,
)


class TestLineChangeWeights:
    """Tests for LineChangeWeights model."""

    def test_default_values(self) -> None:
        """Verify default values for all 4 weight tiers."""
        weights = LineChangeWeights()
        assert weights.small == 0
        assert weights.medium == 1
        assert weights.large == 2
        assert weights.xlarge == 3

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        weights = LineChangeWeights(small=5, medium=10, large=15, xlarge=20)
        assert weights.small == 5
        assert weights.medium == 10
        assert weights.large == 15
        assert weights.xlarge == 20


class TestFileChangeWeights:
    """Tests for FileChangeWeights model."""

    def test_default_values(self) -> None:
        """Verify default values for all 3 weight tiers."""
        weights = FileChangeWeights()
        assert weights.small == 0
        assert weights.medium == 1
        assert weights.large == 2

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        weights = FileChangeWeights(small=3, medium=6, large=9)
        assert weights.small == 3
        assert weights.medium == 6
        assert weights.large == 9


class TestModuleChangeWeights:
    """Tests for ModuleChangeWeights model."""

    def test_default_values(self) -> None:
        """Verify default values for all 3 weight tiers."""
        weights = ModuleChangeWeights()
        assert weights.small == 0
        assert weights.medium == 1
        assert weights.large == 2

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        weights = ModuleChangeWeights(small=1, medium=2, large=3)
        assert weights.small == 1
        assert weights.medium == 2
        assert weights.large == 3


class TestSizeThreshold:
    """Tests for SizeThreshold model."""

    def test_default_values(self) -> None:
        """Verify default threshold values."""
        threshold = SizeThreshold()
        assert threshold.small == 50
        assert threshold.medium == 200
        assert threshold.large == 500

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        threshold = SizeThreshold(small=10, medium=100, large=1000)
        assert threshold.small == 10
        assert threshold.medium == 100
        assert threshold.large == 1000


class TestPRScoringWeights:
    """Tests for PRScoringWeights model."""

    def test_default_values(self) -> None:
        """Verify all 7 fields have correct defaults."""
        weights = PRScoringWeights()
        # Nested weight models
        assert weights.changed_lines.small == 0
        assert weights.changed_lines.medium == 1
        assert weights.changed_lines.large == 2
        assert weights.changed_lines.xlarge == 3

        assert weights.changed_files.small == 0
        assert weights.changed_files.medium == 1
        assert weights.changed_files.large == 2

        assert weights.impacted_modules.small == 0
        assert weights.impacted_modules.medium == 1
        assert weights.impacted_modules.large == 2

        # Integer fields
        assert weights.critical_path_touch == 2
        assert weights.public_api_touch == 2
        assert weights.cross_module_symbol_change == 2
        assert weights.codex_major == 3
        assert weights.codex_critical == 5

    def test_nested_models_match_standalone_defaults(self) -> None:
        """Verify nested model defaults match their standalone model defaults."""
        weights = PRScoringWeights()
        assert weights.changed_lines == LineChangeWeights()
        assert weights.changed_files == FileChangeWeights()
        assert weights.impacted_modules == ModuleChangeWeights()

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        weights = PRScoringWeights(
            changed_lines=LineChangeWeights(small=1, medium=2, large=3, xlarge=4),
            changed_files=FileChangeWeights(small=2, medium=4, large=6),
            impacted_modules=ModuleChangeWeights(small=1, medium=3, large=5),
            critical_path_touch=5,
            public_api_touch=10,
            cross_module_symbol_change=15,
            codex_major=20,
            codex_critical=25,
        )
        assert weights.changed_lines.small == 1
        assert weights.changed_files.medium == 4
        assert weights.impacted_modules.large == 5
        assert weights.critical_path_touch == 5
        assert weights.public_api_touch == 10


class TestPRScoringThresholds:
    """Tests for PRScoringThresholds model."""

    def test_default_values(self) -> None:
        """Verify ascending default thresholds."""
        thresholds = PRScoringThresholds()
        assert thresholds.medium == 3
        assert thresholds.high == 6
        assert thresholds.critical == 9

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        thresholds = PRScoringThresholds(medium=5, high=10, critical=15)
        assert thresholds.medium == 5
        assert thresholds.high == 10
        assert thresholds.critical == 15


class TestMergeGateConfig:
    """Tests for MergeGateConfig model."""

    def test_default_values(self) -> None:
        """Verify default configuration."""
        config = MergeGateConfig()
        assert config.block_on_score_at_or_above == 9
        assert config.block_on_verdict == ["MAJOR", "BLOCK", "REFUSE", "UNKNOWN"]

    def test_list_not_shared_across_instances(self) -> None:
        """Verify list instances are not shared (Pydantic default_factory safety)."""
        config1 = MergeGateConfig()
        config2 = MergeGateConfig()
        # Must be equal but NOT the same object
        assert config1.block_on_verdict == config2.block_on_verdict
        assert config1.block_on_verdict is not config2.block_on_verdict

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        config = MergeGateConfig(
            block_on_score_at_or_above=5,
            block_on_verdict=["MAJOR", "BLOCK"],
        )
        assert config.block_on_score_at_or_above == 5
        assert config.block_on_verdict == ["MAJOR", "BLOCK"]


class TestSizeThresholds:
    """Tests for SizeThresholds model."""

    def test_default_values(self) -> None:
        """Verify all 3 size thresholds have correct defaults."""
        thresholds = SizeThresholds()

        # changed_lines uses base SizeThreshold defaults
        assert thresholds.changed_lines.small == 50
        assert thresholds.changed_lines.medium == 200
        assert thresholds.changed_lines.large == 500

        # changed_files uses custom values
        assert thresholds.changed_files.small == 4
        assert thresholds.changed_files.medium == 10
        assert thresholds.changed_files.large == 20

        # impacted_modules uses custom values
        assert thresholds.impacted_modules.small == 2
        assert thresholds.impacted_modules.medium == 5
        assert thresholds.impacted_modules.large == 10

    def test_custom_values(self) -> None:
        """Verify custom values can be set via constructor."""
        thresholds = SizeThresholds(
            changed_lines=SizeThreshold(small=100, medium=400, large=1000),
            changed_files=SizeThreshold(small=5, medium=15, large=30),
            impacted_modules=SizeThreshold(small=3, medium=8, large=15),
        )
        assert thresholds.changed_lines.small == 100
        assert thresholds.changed_files.medium == 15
        assert thresholds.impacted_modules.large == 15


class TestPRScoringConfig:
    """Tests for PRScoringConfig model."""

    def test_default_values(self) -> None:
        """Verify all 4 nested fields instantiate with correct defaults."""
        config = PRScoringConfig()

        # Verify size_thresholds
        assert config.size_thresholds.changed_lines.small == 50
        assert config.size_thresholds.changed_files.small == 4
        assert config.size_thresholds.impacted_modules.small == 2

        # Verify weights
        assert config.weights.changed_lines.small == 0
        assert config.weights.critical_path_touch == 2
        assert config.weights.codex_critical == 5

        # Verify thresholds
        assert config.thresholds.medium == 3
        assert config.thresholds.high == 6
        assert config.thresholds.critical == 9

        # Verify merge_gate
        assert config.merge_gate.block_on_score_at_or_above == 9
        assert config.merge_gate.block_on_verdict == [
            "MAJOR",
            "BLOCK",
            "REFUSE",
            "UNKNOWN",
        ]

    def test_nested_defaults_match_standalone_models(self) -> None:
        """Verify nested defaults match their standalone model defaults."""
        config = PRScoringConfig()
        assert config.size_thresholds == SizeThresholds()
        assert config.weights == PRScoringWeights()
        assert config.thresholds == PRScoringThresholds()
        assert config.merge_gate == MergeGateConfig()

    def test_custom_values_propagate_correctly(self) -> None:
        """Verify custom constructor overrides propagate correctly."""
        config = PRScoringConfig(
            size_thresholds=SizeThresholds(
                changed_lines=SizeThreshold(small=100, medium=400, large=1000),
                changed_files=SizeThreshold(small=5, medium=15, large=30),
                impacted_modules=SizeThreshold(small=3, medium=8, large=15),
            ),
            weights=PRScoringWeights(
                changed_lines=LineChangeWeights(small=1, medium=2, large=3, xlarge=4),
                critical_path_touch=10,
            ),
            thresholds=PRScoringThresholds(medium=5, high=10, critical=15),
            merge_gate=MergeGateConfig(block_on_score_at_or_above=7),
        )

        # Verify size_thresholds override
        assert config.size_thresholds.changed_lines.small == 100
        assert config.size_thresholds.changed_files.medium == 15

        # Verify weights override
        assert config.weights.changed_lines.small == 1
        assert config.weights.critical_path_touch == 10

        # Verify thresholds override
        assert config.thresholds.medium == 5
        assert config.thresholds.critical == 15

        # Verify merge_gate override
        assert config.merge_gate.block_on_score_at_or_above == 7
