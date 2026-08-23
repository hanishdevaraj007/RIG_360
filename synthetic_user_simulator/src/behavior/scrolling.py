"""Randomized scrolling, used by behavior/scheduler.py to vary in-session activity.

Per README.md Section 12: this generates varied synthetic workload for
load testing. It is not a human-mimicry or detection-avoidance mechanism.
"""

from __future__ import annotations

from playwright.async_api import Page

from src.utils.randomization import Randomizer


async def random_scroll(page: Page, randomizer: Randomizer) -> None:
    """Scroll the page by a random vertical amount.

    Args:
        page: Page to scroll.
        randomizer: Source of randomization for the scroll distance.

    Raises:
        Nothing is caught here -- Playwright errors (e.g. page closed
        mid-scroll) propagate to the caller, which is expected to be
        behavior/scheduler.py, itself called from within a session's
        try/except boundary (see README.md Section 18).
    """
    scroll_amount = randomizer.uniform_int(-300, 800)
    await page.evaluate(f"window.scrollBy(0, {scroll_amount})")