"""Unit tests for the DispatchLifecycle FSM (issue #3220 Phase 1)."""

import pytest

from vibe3.domain.dispatch_lifecycle import (
    DispatchLifecycle,
    DispatchLifecycleConfig,
    DispatchState,
)


class TestColdStart:
    """Fresh FSM defaults."""

    def test_new_fsm_starts_active(self) -> None:
        fsm = DispatchLifecycle()
        assert fsm.state is DispatchState.ACTIVE

    def test_new_fsm_has_zero_idle_ticks(self) -> None:
        fsm = DispatchLifecycle()
        assert fsm.idle_ticks == 0

    def test_new_fsm_is_not_sleeping(self) -> None:
        fsm = DispatchLifecycle()
        assert fsm.is_sleeping is False

    def test_default_config_values(self) -> None:
        config = DispatchLifecycleConfig()
        assert config.refresh_interval_ticks == 10
        assert config.idle_threshold_ticks == 4


class TestActiveTransitions:
    """ACTIVE-state behavior: idle counting and sleep transition."""

    def test_dispatch_resets_idle_and_stays_active(self) -> None:
        fsm = DispatchLifecycle()
        fsm.on_tick(0)
        fsm.on_tick(0)
        assert fsm.idle_ticks == 2
        fsm.on_tick(3)
        assert fsm.state is DispatchState.ACTIVE
        assert fsm.idle_ticks == 0

    def test_idle_increments_each_idle_tick(self) -> None:
        fsm = DispatchLifecycle()
        for _ in range(3):
            fsm.on_tick(0)
        assert fsm.idle_ticks == 3
        assert fsm.state is DispatchState.ACTIVE

    def test_transitions_to_sleeping_at_threshold(self) -> None:
        fsm = DispatchLifecycle()
        for _ in range(4):
            fsm.on_tick(0)
        assert fsm.state is DispatchState.SLEEPING
        assert fsm.idle_ticks == 4

    def test_stays_active_below_threshold(self) -> None:
        fsm = DispatchLifecycle()
        for _ in range(3):
            fsm.on_tick(0)
        assert fsm.state is DispatchState.ACTIVE

    def test_custom_threshold_respected(self) -> None:
        fsm = DispatchLifecycle(DispatchLifecycleConfig(idle_threshold_ticks=2))
        fsm.on_tick(0)
        assert fsm.state is DispatchState.ACTIVE
        fsm.on_tick(0)
        assert fsm.state is DispatchState.SLEEPING


class TestSleepingTransitions:
    """SLEEPING-state behavior: wake on dispatch, persist otherwise."""

    def test_dispatch_wakes_from_sleeping(self) -> None:
        fsm = DispatchLifecycle()
        for _ in range(4):
            fsm.on_tick(0)
        assert fsm.is_sleeping is True
        fsm.on_tick(1)
        assert fsm.state is DispatchState.ACTIVE
        assert fsm.idle_ticks == 0

    def test_continued_idle_stays_sleeping(self) -> None:
        fsm = DispatchLifecycle()
        for _ in range(4):
            fsm.on_tick(0)
        fsm.on_tick(0)
        fsm.on_tick(0)
        assert fsm.state is DispatchState.SLEEPING

    def test_is_sleeping_flag_tracks_state(self) -> None:
        fsm = DispatchLifecycle()
        assert fsm.is_sleeping is False
        for _ in range(4):
            fsm.on_tick(0)
        assert fsm.is_sleeping is True


class TestShouldCollect:
    """Scheduled full-collect tick gate."""

    def test_collects_on_multiple_of_refresh_interval(self) -> None:
        fsm = DispatchLifecycle()
        for tick_id in (10, 20, 30):
            assert fsm.should_collect(tick_id) is True

    def test_does_not_collect_between_intervals(self) -> None:
        fsm = DispatchLifecycle()
        for tick_id in (1, 5, 9, 11, 23):
            assert fsm.should_collect(tick_id) is False

    def test_custom_refresh_interval(self) -> None:
        fsm = DispatchLifecycle(DispatchLifecycleConfig(refresh_interval_ticks=5))
        assert fsm.should_collect(5) is True
        assert fsm.should_collect(10) is True
        assert fsm.should_collect(7) is False


class TestReset:
    """Manual reset returns initial state."""

    def test_reset_returns_to_active_with_zero_idle(self) -> None:
        fsm = DispatchLifecycle()
        for _ in range(4):
            fsm.on_tick(0)
        assert fsm.is_sleeping is True
        fsm.reset()
        assert fsm.state is DispatchState.ACTIVE
        assert fsm.idle_ticks == 0
        assert fsm.is_sleeping is False


class TestConfigValidation:
    """Pydantic validation on config fields."""

    def test_rejects_zero_refresh_interval(self) -> None:
        with pytest.raises(ValueError):
            DispatchLifecycleConfig(refresh_interval_ticks=0)

    def test_rejects_zero_idle_threshold(self) -> None:
        with pytest.raises(ValueError):
            DispatchLifecycleConfig(idle_threshold_ticks=0)
