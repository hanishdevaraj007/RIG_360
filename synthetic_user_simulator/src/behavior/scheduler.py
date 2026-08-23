"""Behavior scheduler -- drives a session's in-page activity for its watch duration.

Composes scrolling.py and mouse.py: while the session's randomized watch
duration hasn't elapsed, periodically perform a randomly-chosen action
(scroll or mouse move) with a randomized interval between actions.

This function is a plain `await`-chain, so it responds normally to
asyncio task cancellation (e.g. on Ctrl+C shutdown, per README.md
Section 28) -- no special cancellation handling is needed here, it's
handled by whatever wraps this call in the orchestrator.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Coroutine, List

from playwright.async_api import Page

from src.behavior.mouse import random_mouse_move
from src.behavior.scrolling import random_scroll
from src.utils.randomization import Randomizer

# Bounds for the gap between randomized in-page actions during the watch
# period. Kept as module constants (rather than config) since this is a
# secondary behavior-pacing detail, not a primary tunable -- if you want
# this configurable later, it's a one-line AppConfig addition plus
# threading it through here.
_MIN_ACTION_INTERVAL_SECONDS = 3.0
_MAX_ACTION_INTERVAL_SECONDS = 10.0

ActionFn = Callable[[Page, Randomizer], Coroutine[None, None, None]]

_ACTIONS: List[ActionFn] = [random_scroll, random_mouse_move]


async def run_watch_behavior(
    page: Page,
    randomizer: Randomizer,
    watch_duration_seconds: float,
    min_action_interval_seconds: float = _MIN_ACTION_INTERVAL_SECONDS,
    max_action_interval_seconds: float = _MAX_ACTION_INTERVAL_SECONDS,
) -> int:
    """Run randomized scroll/mouse actions for approximately watch_duration_seconds.

    Args:
        page: The session's Page.
        randomizer: This session's Randomizer (see Randomizer.child() in
            utils/randomization.py for how sessions get independent RNGs).
        watch_duration_seconds: Total time to spend in this behavior loop.
        min_action_interval_seconds: Minimum gap between actions.
        max_action_interval_seconds: Maximum gap between actions.

    Returns:
        The number of actions actually performed, for logging.

    Raises:
        ValueError: if watch_duration_seconds < 0, or if the interval
            bounds are inconsistent (max < min).
        Exception: any Playwright error from the underlying scroll/mouse
            calls propagates unchanged -- this function does not swallow
            errors, per README.md Section 18 (error handling boundaries
            belong to the caller, not silently here).
    """
    if watch_duration_seconds < 0:
        raise ValueError("watch_duration_seconds must be >= 0")
    if max_action_interval_seconds < min_action_interval_seconds:
        raise ValueError(
            "max_action_interval_seconds must be >= min_action_interval_seconds"
        )

    start = time.monotonic()
    actions_performed = 0

    while True:
        elapsed = time.monotonic() - start
        remaining = watch_duration_seconds - elapsed
        if remaining <= 0:
            break

        interval = randomizer.uniform_float(
            min_action_interval_seconds, max_action_interval_seconds
        )
        sleep_time = min(interval, remaining)
        await asyncio.sleep(sleep_time)

        elapsed = time.monotonic() - start
        if elapsed >= watch_duration_seconds:
            break

        action = randomizer.choice(_ACTIONS)
        await action(page, randomizer)
        actions_performed += 1

    return actions_performed