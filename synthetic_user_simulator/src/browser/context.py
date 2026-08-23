"""Per-session Playwright BrowserContext creation.

One BrowserContext == one isolated "browser profile" (cookies, storage,
viewport, etc.) within a single shared Browser process. This is where
compatibility-testing parameters (viewport, locale, timezone, user-agent)
and, for DNL sessions only, proxy assignment are applied.

Per README.md Section 4: these options exist for cross-device/browser
compatibility testing, not to construct a unique "fingerprint" intended
to evade detection. No fingerprint-spoofing or stealth libraries are
used here or anywhere else in this project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Browser, BrowserContext


class ContextCreationError(Exception):
    """Raised when Playwright fails to create a browser context."""


@dataclass(frozen=True)
class ContextOptions:
    """Typed, validated-by-caller options for one session's browser context.

    proxy_server, if set, must already be in the form Playwright expects,
    e.g. "http://host:port" or "socks5://host:port" -- parsing/validating
    the raw proxy-list line happens in proxy/manager.py (not yet
    implemented), not here. This module only applies an already-parsed
    proxy to the context.
    """

    viewport_width: int = 1280
    viewport_height: int = 720
    locale: str = "en-US"
    timezone_id: Optional[str] = None
    user_agent: Optional[str] = None
    proxy_server: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None


async def create_context(browser: Browser, options: ContextOptions) -> BrowserContext:
    """Create a new isolated BrowserContext from the given options.

    Args:
        browser: A running Browser instance (from BrowserManager.start()).
        options: Context configuration for this session.

    Returns:
        A new BrowserContext. Caller is responsible for closing it
        (typically in the session task's `finally` block).

    Raises:
        ContextCreationError: if Playwright fails to create the context
            (e.g. malformed proxy configuration, invalid locale).
    """
    kwargs: dict = {
        "viewport": {
            "width": options.viewport_width,
            "height": options.viewport_height,
        },
        "locale": options.locale,
    }

    if options.timezone_id:
        kwargs["timezone_id"] = options.timezone_id

    if options.user_agent:
        kwargs["user_agent"] = options.user_agent

    if options.proxy_server:
        proxy_config: dict = {"server": options.proxy_server}
        if options.proxy_username:
            proxy_config["username"] = options.proxy_username
        if options.proxy_password:
            proxy_config["password"] = options.proxy_password
        kwargs["proxy"] = proxy_config

    try:
        return await browser.new_context(**kwargs)
    except Exception as exc:
        raise ContextCreationError(
            f"Failed to create browser context "
            f"(locale={options.locale!r}, "
            f"proxy_set={bool(options.proxy_server)}): {exc}"
        ) from exc