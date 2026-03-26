"""Tests for shared command helper logic in plan_helpers."""

from types import SimpleNamespace

import pytest

from vibe3.commands.plan_helpers import get_agent_options


def _make_config(
    *,
    plan_agent: str | None = None,
    plan_backend: str | None = None,
    plan_model: str | None = None,
    run_agent: str | None = None,
    run_backend: str | None = None,
    run_model: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        plan=SimpleNamespace(
            agent_config=SimpleNamespace(
                agent=plan_agent,
                backend=plan_backend,
                model=plan_model,
            )
        ),
        run=SimpleNamespace(
            agent_config=SimpleNamespace(
                agent=run_agent,
                backend=run_backend,
                model=run_model,
            )
        ),
    )


def test_get_agent_options_uses_run_section_with_backend_model() -> None:
    config = _make_config(run_backend="codex", run_model="gpt-5.3")

    options = get_agent_options(
        config,
        agent=None,
        backend=None,
        model=None,
        section="run",
    )

    assert options.agent is None
    assert options.backend == "codex"
    assert options.model == "gpt-5.3"


def test_get_agent_options_run_section_uses_agent_preset() -> None:
    config = _make_config(run_agent="executor")

    options = get_agent_options(
        config,
        agent=None,
        backend=None,
        model=None,
        section="run",
    )

    assert options.agent == "executor"
    assert options.backend is None
    assert options.model is None


def test_get_agent_options_cli_agent_override_has_highest_priority() -> None:
    config = _make_config(plan_backend="claude", plan_model="sonnet")

    options = get_agent_options(
        config,
        agent="planner-pro",
        backend="codex",
        model="gpt-5.3",
        section="plan",
    )

    assert options.agent == "planner-pro"
    assert options.backend is None
    assert options.model is None


def test_get_agent_options_rejects_invalid_section() -> None:
    config = _make_config()

    with pytest.raises(ValueError, match="Unsupported section"):
        get_agent_options(
            config,
            agent=None,
            backend=None,
            model=None,
            section="invalid",  # type: ignore[arg-type]
        )


def test_get_agent_options_raises_when_no_config() -> None:
    config = _make_config()

    with pytest.raises(ValueError, match="No agent configuration found"):
        get_agent_options(
            config,
            agent=None,
            backend=None,
            model=None,
            section="run",
        )
