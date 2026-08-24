"""Unit tests for src/behavior/*.

Uses a fake Page recording calls, and a real seeded Randomizer, so
these run fast and deterministically without a real browser or actual
wall-clock waiting for long durations.
"""

import asyncio

import pytest

from src.behavior.mouse import random_mouse_move
from src.behavior.scheduler import run_watch_behavior
from src.behavior.scrolling import random_scroll
from src.utils.randomization import Randomizer


class FakeMouse:
    def __init__(self):
        self.moves = []

    async def move(self, x, y):
        self.moves.append((x, y))


class FakePage:
    def __init__(self):
        self.evaluated = []
        self.mouse = FakeMouse()

    async def evaluate(self, script: str):
        self.evaluated.append(script)


# --- scrolling / mouse -----------------------------------------------------

@pytest.mark.asyncio
async def test_random_scroll_calls_evaluate_with_scrollby():
    page = FakePage()
    randomizer = Randomizer(seed=1)
    await random_scroll(page, randomizer)
    assert len(page.evaluated) == 1
    assert "window.scrollBy" in page.evaluated[0]


@pytest.mark.asyncio
async def test_random_mouse_move_calls_mouse_move_within_range():
    page = FakePage()
    randomizer = Randomizer(seed=1)
    await random_mouse_move(page, randomizer, x_range=(0, 100), y_range=(0, 50))
    assert len(page.mouse.moves) == 1
    x, y = page.mouse.moves[0]
    assert 0 <= x <= 100
    assert 0 <= y <= 50


# --- scheduler ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_watch_behavior_zero_duration_performs_no_actions():
    page = FakePage()
    randomizer = Randomizer(seed=1)
    count = await run_watch_behavior(page, randomizer, watch_duration_seconds=0)
    assert count == 0
    assert page.evaluated == []
    assert page.mouse.moves == []


@pytest.mark.asyncio
async def test_run_watch_behavior_short_duration_performs_at_least_one_action():
    page = FakePage()
    randomizer = Randomizer(seed=1)
    count = await run_watch_behavior(
        page,
        randomizer,
        watch_duration_seconds=0.05,
        min_action_interval_seconds=0.01,
        max_action_interval_seconds=0.02,
    )
    assert count >= 1
    assert (len(page.evaluated) + len(page.mouse.moves)) == count


@pytest.mark.asyncio
async def test_run_watch_behavior_negative_duration_raises():
    page = FakePage()
    randomizer = Randomizer(seed=1)
    with pytest.raises(ValueError, match="watch_duration_seconds"):
        await run_watch_behavior(page, randomizer, watch_duration_seconds=-1)


@pytest.mark.asyncio
async def test_run_watch_behavior_bad_interval_bounds_raises():
    page = FakePage()
    randomizer = Randomizer(seed=1)
    with pytest.raises(ValueError, match="max_action_interval_seconds"):
        await run_watch_behavior(
            page,
            randomizer,
            watch_duration_seconds=1,
            min_action_interval_seconds=5,
            max_action_interval_seconds=1,
        )


@pytest.mark.asyncio
async def test_run_watch_behavior_is_reproducible_with_same_seed(monkeypatch):
    import time
    import asyncio

    current_time = 0.0

    def mock_monotonic():
        return current_time

    async def mock_sleep(seconds):
        nonlocal current_time
        current_time += seconds

    monkeypatch.setattr(time, "monotonic", mock_monotonic)
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    page1 = FakePage()
    page2 = FakePage()
    count1 = await run_watch_behavior(
        page1,
        Randomizer(seed=7),
        watch_duration_seconds=0.05,
        min_action_interval_seconds=0.01,
        max_action_interval_seconds=0.02,
    )

    current_time = 0.0

    count2 = await run_watch_behavior(
        page2,
        Randomizer(seed=7),
        watch_duration_seconds=0.05,
        min_action_interval_seconds=0.01,
        max_action_interval_seconds=0.02,
    )
    assert count1 == count2


@pytest.mark.asyncio
async def test_run_watch_behavior_propagates_cancellation():
    page = FakePage()
    randomizer = Randomizer(seed=1)

    async def run():
        await run_watch_behavior(
            page,
            randomizer,
            watch_duration_seconds=10,
            min_action_interval_seconds=5,
            max_action_interval_seconds=5,
        )

    task = asyncio.ensure_future(run())
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task