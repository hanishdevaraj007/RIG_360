"""Playwright browser process lifecycle.

BrowserManager owns exactly one Playwright driver + one browser instance.
It does not know about sessions, platforms, or contexts -- callers create
one BrowserContext per session via browser/context.py using the Browser
this manager returns. Keeping this separate from context creation means
a single browser process can host many concurrent contexts (the normal
Playwright pattern for this kind of workload) rather than one browser
process per session.
"""

from __future__ import annotations

from typing import Optional

from playwright.async_api import Browser, Playwright, async_playwright

SUPPORTED_BROWSER_TYPES = ("chromium", "firefox", "webkit")


class BrowserLaunchError(Exception):
    """Raised when Playwright itself or the browser process fails to start."""


class BrowserManager:
    """Owns a single Playwright driver + browser instance.

    Usage:
        manager = BrowserManager(headless=True, browser_type="chromium")
        browser = await manager.start()
        ...
        await manager.close()

    Or as an async context manager:
        async with BrowserManager(headless=True) as browser:
            ...
    """

    def __init__(self, headless: bool = True, browser_type: str = "chromium") -> None:
        """
        Args:
            headless: Run without a visible browser window.
            browser_type: One of "chromium", "firefox", "webkit".

        Raises:
            BrowserLaunchError: if browser_type is not supported, raised
                immediately rather than deferred to start().
        """
        if browser_type not in SUPPORTED_BROWSER_TYPES:
            raise BrowserLaunchError(
                f"Unsupported browser_type '{browser_type}'; "
                f"must be one of {SUPPORTED_BROWSER_TYPES}"
            )
        self.headless = headless
        self.browser_type = browser_type
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def start(self) -> Browser:
        """Start Playwright and launch the browser, if not already running.

        Idempotent: calling start() again while already running returns
        the existing Browser instead of launching a second one.

        Returns:
            The running Browser instance.

        Raises:
            BrowserLaunchError: if Playwright fails to start or the
                browser process fails to launch. Any partially-started
                Playwright driver is cleaned up before the error is
                raised, so a failed start() never leaks a driver process.
        """
        if self._browser is not None:
            return self._browser

        try:
            self._playwright = await async_playwright().start()
        except Exception as exc:
            self._playwright = None
            raise BrowserLaunchError(
                f"Failed to start Playwright driver: {exc}"
            ) from exc

        try:
            launcher = getattr(self._playwright, self.browser_type)
            self._browser = await launcher.launch(headless=self.headless)
        except Exception as exc:
            await self._cleanup_playwright()
            raise BrowserLaunchError(
                f"Failed to launch {self.browser_type} "
                f"(headless={self.headless}): {exc}"
            ) from exc

        return self._browser

    async def close(self) -> None:
        """Close the browser and stop the Playwright driver.

        Safe to call multiple times and safe to call even if start()
        was never successfully completed.
        """
        if self._browser is not None:
            try:
                await self._browser.close()
            finally:
                self._browser = None
        await self._cleanup_playwright()

    async def _cleanup_playwright(self) -> None:
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            finally:
                self._playwright = None

    async def __aenter__(self) -> Browser:
        return await self.start()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()