"""YouTube platform adapter -- observation/compatibility-testing only.

Per README.md Section 4 and Section 25, this adapter is deliberately
narrow. It does NOT:
  - use any stealth/anti-fingerprint technique to evade YouTube's bot
    detection,
  - accept or apply a proxy for identity rotation (proxy assignment is
    wired up for DNL sessions only, in the orchestrator, not here),
  - send chat messages (chat sending is not part of the PlatformAdapter
    interface at all -- see platforms/base.py docstring),
  - attempt to bypass CAPTCHA or any rate limiting.

It exists to open a public video/stream URL and report, honestly, what
was observed: did the page load, did a <video> element appear, does it
look like playback started. Nothing here should be read as a guarantee
that YouTube's UI will behave the same way tomorrow -- it's a third-party
site outside this project's control (see README.md Section 25).
"""

from __future__ import annotations

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.platforms.base import PlatformAdapter, PlatformError, PlaybackObservation

# How long to wait for basic page load / a <video> element to appear.
# This is a compatibility-observation timeout, not a retry/evasion
# mechanism -- if YouTube doesn't load in time, we report that honestly
# as a PlatformError rather than looping or working around it.
_DEFAULT_NAVIGATION_TIMEOUT_MS = 30_000
_VIDEO_ELEMENT_TIMEOUT_MS = 15_000
_VIDEO_ELEMENT_SELECTOR = "video"


class YouTubeAdapter(PlatformAdapter):
    """Observation-only adapter for public YouTube video/stream URLs."""

    platform_name = "youtube"

    def __init__(
        self,
        navigation_timeout_ms: int = _DEFAULT_NAVIGATION_TIMEOUT_MS,
        video_element_timeout_ms: int = _VIDEO_ELEMENT_TIMEOUT_MS,
    ) -> None:
        """
        Args:
            navigation_timeout_ms: Max time to wait for page.goto() to
                consider the page loaded.
            video_element_timeout_ms: Max time to wait for a <video>
                element to appear after navigation, before giving up on
                detecting it (does not fail the whole session -- see
                observe_playback).
        """
        self.navigation_timeout_ms = navigation_timeout_ms
        self.video_element_timeout_ms = video_element_timeout_ms

    async def open_stream(self, page: Page, target_url: str) -> None:
        """Navigate to a YouTube video/stream URL.

        Args:
            page: Playwright Page to navigate.
            target_url: A YouTube video/watch/live URL.

        Raises:
            PlatformError: if navigation fails or times out. This is
                reported honestly rather than retried indefinitely or
                worked around -- a failed load is a valid, useful test
                result.
        """
        try:
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=self.navigation_timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise PlatformError(
                f"YouTube navigation to {target_url!r} timed out after "
                f"{self.navigation_timeout_ms}ms: {exc}"
            ) from exc
        except Exception as exc:
            raise PlatformError(
                f"YouTube navigation to {target_url!r} failed: {exc}"
            ) from exc

    async def observe_playback(self, page: Page) -> PlaybackObservation:
        """Check whether the page loaded and a video element is playing.

        Detection method: look for a <video> element and, if found,
        evaluate its `paused` and `currentTime` properties. This is a
        simple, honest signal -- it is not a claim about YouTube's
        internal player state machine, ad state, or buffering status.

        Args:
            page: The Page previously passed to open_stream().

        Returns:
            PlaybackObservation with page_loaded reflecting whether the
            page has a title at all, and playback_started reflecting
            whether a <video> element was found with currentTime > 0
            and not paused. If no <video> element is found within the
            timeout, playback_started is False and `detail` explains why
            -- this is not treated as a PlatformError, since "no video
            element yet" is itself a valid, loggable observation.

        Raises:
            PlatformError: if the page itself cannot be queried at all
                (e.g. it crashed or was closed).

        Known limitation (verified, not yet fixed): if the caller is
        cancelled while this is awaiting wait_for_selector() AND the
        browser context is closed around the same moment (the exact
        sequence orchestrator/runner.py's shutdown path produces),
        Playwright's own internal wait future can be left orphaned and
        logs "Future exception was never retrieved" to stderr. This does
        not corrupt results, hang the process, or affect
        SessionResult/JSONL output (verified by running a cancellation
        under load) -- it is cosmetic stderr noise from Playwright's
        internals, not something this adapter's own exception handling
        can suppress. See README.md Section 21 (Troubleshooting).
        """
        try:
            title = await page.title()
        except Exception as exc:
            raise PlatformError(f"Could not read YouTube page state: {exc}") from exc

        page_loaded = bool(title)

        try:
            video_handle = await page.wait_for_selector(
                _VIDEO_ELEMENT_SELECTOR,
                timeout=self.video_element_timeout_ms,
            )
        except PlaywrightTimeoutError:
            return PlaybackObservation(
                page_loaded=page_loaded,
                playback_started=False,
                detail="no <video> element detected within timeout",
            )

        try:
            state = await video_handle.evaluate(
                "el => ({paused: el.paused, currentTime: el.currentTime})"
            )
        except Exception as exc:
            return PlaybackObservation(
                page_loaded=page_loaded,
                playback_started=False,
                detail=f"<video> element found but state could not be read: {exc}",
            )

        playback_started = (not state.get("paused", True)) and state.get(
            "currentTime", 0
        ) > 0

        return PlaybackObservation(
            page_loaded=page_loaded,
            playback_started=playback_started,
            detail=(
                f"paused={state.get('paused')}, "
                f"currentTime={state.get('currentTime')}"
            ),
        )

    async def close(self, page: Page) -> None:
        """No platform-specific teardown is required for YouTube.

        Context/page closing itself is handled by the orchestrator, not
        here -- this is intentionally a no-op, present only to satisfy
        the PlatformAdapter interface.
        """
        return None