"""Randomized mouse movement, used by behavior/scheduler.py to vary in-session activity.

Per README.md Section 12: this generates varied synthetic workload for
load testing. It is not a human-mimicry or detection-avoidance mechanism,
and no attempt is made to model realistic human mouse-movement curves.
"""

from __future__ import annotations

from playwright.async_api import Page

from src.utils.randomization import Randomizer

# Kept modest and within typical viewport bounds; callers using a
# non-default viewport size should be aware coordinates aren't clamped
# to the actual viewport here (viewport size isn't known to this
# function) -- this is a known simplification, not a hidden assumption.
_DEFAULT_X_RANGE = (0, 1280)
_DEFAULT_Y_RANGE = (0, 720)


async def random_mouse_move(
    page: Page,
    randomizer: Randomizer,
    x_range: tuple[int, int] = _DEFAULT_X_RANGE,
    y_range: tuple[int, int] = _DEFAULT_Y_RANGE,
) -> None:
    """Move the mouse to a random point within the given ranges.

    Args:
        page: Page whose mouse to move.
        randomizer: Source of randomization for the target coordinates.
        x_range: (min, max) horizontal pixel bounds.
        y_range: (min, max) vertical pixel bounds.

    Raises:
        Nothing is caught here -- see random_scroll()'s docstring for
        the same rationale.
    """
    target_x = randomizer.uniform_int(*x_range)
    target_y = randomizer.uniform_int(*y_range)
    await page.mouse.move(target_x, target_y)