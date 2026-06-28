"""Tests for dispatch sleep-mode collection throttling (issues #3220, #3233).

When the DispatchLifecycle FSM enters SLEEPING (sustained inactivity),
``_should_collect_after_dispatch`` throttles collection to scheduled refresh
ticks (``tick_id % refresh_interval == 0``) to save GitHub API calls. While
ACTIVE, the existing collection logic (paused-always-collect, capacity gate,
actionable check) is unchanged.

The paused gate precedes the sleep gate (#3233 Finding 4): paused is the
stronger, content-based exhaustion signal and must always re-verify, even
when the FSM is simultaneously SLEEPING.
"""

from __future__ import annotations

from collections.abc import Callable

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator

_MakeCoordinator = Callable[..., GlobalDispatchCoordinator]


def _sleeping_coordinator(
    make_coordinator: _MakeCoordinator,
) -> GlobalDispatchCoordinator:
    """Build a coordinator whose FSM has entered SLEEPING (4 idle ticks)."""
    coordinator = make_coordinator("manager")
    for _ in range(4):
        coordinator._dispatch_lifecycle.on_tick(0)
    assert coordinator._dispatch_lifecycle.is_sleeping
    return coordinator


def test_sleep_mode_collects_on_refresh_interval(
    make_coordinator: _MakeCoordinator,
) -> None:
    """While sleeping, collection runs on ticks divisible by refresh_interval."""
    coordinator = _sleeping_coordinator(make_coordinator)
    coordinator._current_tick_id = 20
    assert coordinator._should_collect_after_dispatch(0) is True
    coordinator._current_tick_id = 30
    assert coordinator._should_collect_after_dispatch(0) is True


def test_sleep_mode_throttles_between_refresh_intervals(
    make_coordinator: _MakeCoordinator,
) -> None:
    """While sleeping, collection is skipped between refresh ticks."""
    coordinator = _sleeping_coordinator(make_coordinator)
    for tick_id in (1, 5, 9, 11, 23):
        coordinator._current_tick_id = tick_id
        assert coordinator._should_collect_after_dispatch(0) is False


def test_active_mode_preserves_paused_always_collect(
    make_coordinator: _MakeCoordinator,
) -> None:
    """While ACTIVE (not sleeping), structural pause still forces collection."""
    coordinator = make_coordinator("manager")
    assert coordinator._dispatch_lifecycle.is_sleeping is False
    coordinator._dispatch_paused = True
    assert coordinator._should_collect_after_dispatch(0) is True


def test_paused_gate_precedes_sleep_gate(
    make_coordinator: _MakeCoordinator,
) -> None:
    """While SLEEPING and paused, paused wins: collection always runs.

    Regression for #3233 Finding 4: the paused gate must precede the sleep
    gate so that content-based exhaustion re-verifies every tick, even when
    the FSM's activity counter would otherwise throttle collection.
    """
    coordinator = _sleeping_coordinator(make_coordinator)
    coordinator._dispatch_paused = True
    for tick_id in (1, 5, 9, 11, 23):
        coordinator._current_tick_id = tick_id
        assert coordinator._should_collect_after_dispatch(0) is True
