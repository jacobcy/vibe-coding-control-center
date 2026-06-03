"""Tests for public API exports across all packages."""


def test_models_verdict_record_importable():
    from vibe3.models import VerdictRecord

    assert VerdictRecord is not None


def test_models_verdict_value_importable():
    from vibe3.models import VerdictValue

    assert VerdictValue is not None


def test_models_agent_options_importable():
    from vibe3.models import AgentOptions

    assert AgentOptions is not None


def test_models_all_contains_verdict_symbols():
    from vibe3.models import __all__

    assert "VerdictRecord" in __all__
    assert "VerdictValue" in __all__
    assert "AgentOptions" in __all__
