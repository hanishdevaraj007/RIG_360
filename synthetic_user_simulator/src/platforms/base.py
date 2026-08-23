"""Platform adapter abstraction.

A PlatformAdapter isolates everything platform-specific (selectors, page
structure, navigation quirks) behind one small interface, so orchestrator/
browser/behavior code never references DNL or YouTube directly.

Deliberately NOT part of this interface: chat sending. Chat is a separate
abstraction (chat/base.py, next stage) with its own lifecycle, and per
README.md Section 4 it is only implemented for DNL -- keeping it out of
PlatformAdapter means YouTubeAdapter has no chat-shaped method to
accidentally misuse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Page


class PlatformError(Exception):
    """Raised when a platform adapter cannot complete a requested action.

    Distinct from BrowserLaunchError/ContextCreationError (browser/) and
    NavigationError (introduced when navigation is implemented) so a
    caller can tell "the browser is broken" apart from "this platform's
    page didn't behave as expected."
    """


@dataclass(frozen=True)
class PlaybackObservation:
    """Result of observing a platform's page/player after opening a stream.

    This is intentionally an *observation*, not a claim of success --
    fields describe what was detected, not what was intended. Adapters
    must not report `playback_started=True` unless they actually
    detected evidence of it (e.g. a player-state check), per the
    no-hallucination rule: we don't assume playback started just because
    navigation succeeded.
    """

    page_loaded: bool
    playback_started: bool
    detail: Optional[str] = None


class PlatformAdapter(ABC):
    """Interface every platform adapter (DNL, YouTube) must implement.

    Concrete subclasses are responsible only for platform-specific
    interaction with a Playwright Page. They do not create browsers,
    contexts, or pages themselves -- those are handed to them by the
    orchestrator (not yet implemented), which keeps adapters trivially
    testable with a fake Page.
    """

    #: Short identifier used in config (`platform: dnl` / `platform: youtube`)
    #: and in logs. Concrete subclasses must override this.
    platform_name: str = "base"

    @abstractmethod
    async def open_stream(self, page: Page, target_url: str) -> None:
        """Navigate to target_url and reach the point of attempting playback.

        Args:
            page: An already-created Playwright Page (from a session's
                BrowserContext).
            target_url: The stream/video URL to open.

        Raises:
            PlatformError: if navigation fails or the expected page
                structure is not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def observe_playback(self, page: Page) -> PlaybackObservation:
        """Check whether the page loaded and playback appears to have started.

        Must reflect what was actually detected on the page -- never
        return playback_started=True without a concrete check backing it.

        Args:
            page: The Page previously passed to open_stream().

        Returns:
            A PlaybackObservation describing what was detected.

        Raises:
            PlatformError: if the page state cannot be determined at all
                (e.g. page crashed).
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self, page: Page) -> None:
        """Perform any platform-specific teardown before the page/context closes.

        For most adapters this may be a no-op, but it's part of the
        interface so a platform that needs explicit cleanup (e.g.
        leaving a stream gracefully) has a defined place to do it.

        Args:
            page: The Page used for this session.
        """
        raise NotImplementedError