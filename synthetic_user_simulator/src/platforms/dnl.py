"""DNL platform adapter -- STUB pending real DNL page/DOM integration details.

TODO(DNL-INTEGRATION): the real DNL page structure, player selectors,
and (if required) authentication flow have not been supplied. See
README.md Section 23 (DNL Integration Points).

Per the project's no-hallucination rule, every method here raises
PlatformError immediately and explicitly, rather than guessing at
selectors that don't exist or silently no-op'ing in a way that would let
a session appear to succeed without actually doing anything.
"""

from __future__ import annotations

from playwright.async_api import Page

from src.platforms.base import PlatformAdapter, PlatformError, PlaybackObservation


class DNLAdapter(PlatformAdapter):
    """Non-functional stub. Every call raises PlatformError until real
    DNL selectors/DOM structure are supplied -- see README.md Section 23.
    """

    platform_name = "dnl"

    async def open_stream(self, page: Page, target_url: str) -> None:
        """Not implemented -- see class docstring and README.md Section 23.

        Raises:
            PlatformError: always, until real DNL selectors are supplied.
        """
        raise PlatformError(
            "DNLAdapter.open_stream is not implemented -- DNL page "
            "structure and player selectors have not been supplied. "
            "See README.md Section 23 (DNL Integration Points)."
        )

    async def observe_playback(self, page: Page) -> PlaybackObservation:
        """Not implemented -- see class docstring and README.md Section 23.

        Raises:
            PlatformError: always, until real DNL selectors are supplied.
        """
        raise PlatformError(
            "DNLAdapter.observe_playback is not implemented -- DNL "
            "player state selectors have not been supplied. See "
            "README.md Section 23 (DNL Integration Points)."
        )

    async def close(self, page: Page) -> None:
        """No-op. Safe to call even though open_stream() always raises
        first in the current stub, so this is never reached in normal
        session flow -- it exists to satisfy the PlatformAdapter
        interface and to already be correct once DNLAdapter becomes real.
        """
        return None