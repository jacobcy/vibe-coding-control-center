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


def test_config_get_role_output_contract_importable():
    from vibe3.config import get_role_output_contract

    assert callable(get_role_output_contract)


def test_config_get_role_section_importable():
    from vibe3.config import get_role_section

    assert callable(get_role_section)


def test_config_governance_gate_config_importable():
    from vibe3.config import GOVERNANCE_GATE_CONFIG

    assert GOVERNANCE_GATE_CONFIG is not None


def test_config_resolve_effective_agent_options_importable():
    from vibe3.config import resolve_effective_agent_options

    assert callable(resolve_effective_agent_options)


def test_config_all_contains_role_symbols():
    from vibe3.config import __all__

    assert "get_role_output_contract" in __all__
    assert "get_role_section" in __all__
    assert "GOVERNANCE_GATE_CONFIG" in __all__
    assert "resolve_effective_agent_options" in __all__


def test_agents_sync_models_json_importable():
    from vibe3.agents import sync_models_json

    assert callable(sync_models_json)


def test_agents_all_contains_sync_models_json():
    from vibe3.agents import __all__

    assert "sync_models_json" in __all__
