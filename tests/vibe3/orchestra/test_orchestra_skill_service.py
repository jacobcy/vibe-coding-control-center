"""Tests for OrchestraSkillService."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.orchestra_skill_service import OrchestraSkillService


class _ImmediateLoop:
    async def run_in_executor(self, _executor, func, *args):  # type: ignore[no-untyped-def]
        return func(*args)


def _svc(dry_run: bool = True) -> OrchestraSkillService:
    config = OrchestraConfig(
        polling_interval=900,
        dry_run=dry_run,
    )
    return OrchestraSkillService(config)


@pytest.mark.asyncio
async def test_on_tick_triggers_skill_after_interval() -> None:
    svc = _svc(dry_run=True)
    svc._last_trigger = 0.0

    with patch("time.time", return_value=1000.0):
        with patch("asyncio.get_running_loop", return_value=_ImmediateLoop()):
            await svc.on_tick()

    assert svc._last_trigger > 0


@pytest.mark.asyncio
async def test_on_tick_skips_when_interval_not_passed() -> None:
    svc = _svc()
    svc._last_trigger = 900.0

    with patch("time.time", return_value=950.0):
        with patch("asyncio.get_running_loop", return_value=_ImmediateLoop()):
            await svc.on_tick()

    assert svc._last_trigger == 900.0


@pytest.mark.asyncio
async def test_on_tick_skips_when_already_running() -> None:
    svc = _svc()
    svc._last_trigger = 0.0
    svc._running = True

    with patch("time.time", return_value=1000.0):
        with patch("asyncio.get_running_loop", return_value=_ImmediateLoop()):
            await svc.on_tick()

    assert svc._last_trigger == 0.0


def test_dispatch_skill_dry_run() -> None:
    svc = _svc(dry_run=True)
    svc._dispatcher.dispatch_skill = MagicMock()

    svc._dispatch_skill()

    svc._dispatcher.dispatch_skill.assert_not_called()


def test_dispatch_skill_calls_dispatcher() -> None:
    svc = _svc(dry_run=False)
    svc._dispatcher.dispatch_skill = MagicMock(return_value=True)

    svc._dispatch_skill()

    svc._dispatcher.dispatch_skill.assert_called_once_with("vibe-orchestra")
