"""Dispatch lifecycle FSM for queue sleep/wake cycling.

Two-state finite state machine (ACTIVE / SLEEPING) driven by a single
idle_ticks counter (activity-based: consecutive ticks with
dispatched_count == 0).

Role in the dispatch architecture (issues #3220, #3233):
- This FSM throttles *collection frequency* when the queue is idle
  (SLEEPING -> collect on scheduled refresh ticks only), saving GitHub
  API calls. It is wired into GlobalDispatchCoordinator.
- It is intentionally distinct from the structural pause
  (``_dispatch_paused``, content-based: "no dispatchable entry after
  collect+merge") and from ``pool_exhaustion`` (which stops the server
  after sustained structural pause). The three mechanisms measure
  different things and coexist by design.

The single-counter design replaces the dual-counter pool_exhaustion
divergence bug (issue #3220 C1 root cause) for the collection-throttling
concern.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DispatchState(Enum):
    """Two-state FSM for the dispatch queue lifecycle."""

    ACTIVE = "active"
    SLEEPING = "sleeping"


class DispatchLifecycleConfig(BaseModel):
    """Configuration for the DispatchLifecycle FSM."""

    model_config = ConfigDict(frozen=True)

    refresh_interval_ticks: int = Field(
        default=10,
        ge=1,
        description="Full-queue collect when tick_id % N == 0.",
    )
    idle_threshold_ticks: int = Field(
        default=4,
        ge=1,
        description=(
            "Consecutive ticks with dispatched_count == 0 that transition "
            "the FSM from ACTIVE to SLEEPING."
        ),
    )


class DispatchLifecycle:
    """Track dispatch queue activity as a two-state FSM.

    ACTIVE:   dispatch loop runs each tick.
    SLEEPING: reached after idle_threshold_ticks consecutive idle ticks
              (dispatched_count == 0); a scheduled collect tick
              (tick_id % refresh_interval_ticks == 0) is the cheap probe
              that may redispatch and wake the FSM.
    Any tick with dispatched_count > 0 returns the FSM to ACTIVE and
    resets the idle counter.
    """

    def __init__(self, config: DispatchLifecycleConfig | None = None) -> None:
        self._config = config or DispatchLifecycleConfig()
        self._state: DispatchState = DispatchState.ACTIVE
        self._idle_ticks: int = 0

    @property
    def state(self) -> DispatchState:
        """Current FSM state."""
        return self._state

    @property
    def idle_ticks(self) -> int:
        """Consecutive idle ticks (dispatched_count == 0) seen so far."""
        return self._idle_ticks

    @property
    def is_sleeping(self) -> bool:
        """True when the FSM is in SLEEPING state."""
        return self._state is DispatchState.SLEEPING

    def on_tick(self, dispatched_count: int) -> DispatchState:
        """Advance the FSM given this tick's dispatch outcome.

        Returns the resulting state. dispatched_count > 0 wakes the FSM
        to ACTIVE and zeroes the idle counter; otherwise the idle counter
        increments and the FSM sleeps once it reaches the threshold.
        """
        if dispatched_count > 0:
            self._state = DispatchState.ACTIVE
            self._idle_ticks = 0
            return self._state
        self._idle_ticks += 1
        if self._idle_ticks >= self._config.idle_threshold_ticks:
            self._state = DispatchState.SLEEPING
        return self._state

    def should_collect(self, tick_id: int) -> bool:
        """Whether tick_id triggers a scheduled full-queue collect.

        The coordinator additionally forces a collect when the queue is
        empty; this method only encodes the periodic schedule.
        """
        return tick_id % self._config.refresh_interval_ticks == 0
