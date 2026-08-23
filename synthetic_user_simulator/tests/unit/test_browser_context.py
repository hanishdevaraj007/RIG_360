"""Unit tests for src/browser/context.py.

Uses a fake Browser whose new_context() records the kwargs it was called
with, instead of a real Playwright browser -- these tests check that we
build the right options dict, not that Playwright itself works.
"""

import pytest

from src.browser.context import ContextCreationError, ContextOptions, create_context


class FakeBrowserContext:
    def __init__(self, kwargs: dict):
        self.kwargs = kwargs


class FakeBrowser:
    """Stands in for playwright.async_api.Browser in these tests."""

    def __init__(self, raise_on_new_context: bool = False):
        self.raise_on_new_context = raise_on_new_context
        self.last_kwargs: dict = {}

    async def new_context(self, **kwargs):
        self.last_kwargs = kwargs
        if self.raise_on_new_context:
            raise RuntimeError("simulated Playwright failure")
        return FakeBrowserContext(kwargs)


@pytest.mark.asyncio
async def test_minimal_options_produce_viewport_and_locale_only():
    browser = FakeBrowser()
    options = ContextOptions()
    await create_context(browser, options)

    assert browser.last_kwargs["viewport"] == {"width": 1280, "height": 720}
    assert browser.last_kwargs["locale"] == "en-US"
    assert "timezone_id" not in browser.last_kwargs
    assert "user_agent" not in browser.last_kwargs
    assert "proxy" not in browser.last_kwargs


@pytest.mark.asyncio
async def test_full_options_are_all_applied():
    browser = FakeBrowser()
    options = ContextOptions(
        viewport_width=1920,
        viewport_height=1080,
        locale="fr-FR",
        timezone_id="Europe/Paris",
        user_agent="test-agent/1.0",
        proxy_server="http://203.0.113.10:8080",
        proxy_username="testuser",
        proxy_password="testpass",
    )
    await create_context(browser, options)

    kwargs = browser.last_kwargs
    assert kwargs["viewport"] == {"width": 1920, "height": 1080}
    assert kwargs["locale"] == "fr-FR"
    assert kwargs["timezone_id"] == "Europe/Paris"
    assert kwargs["user_agent"] == "test-agent/1.0"
    assert kwargs["proxy"] == {
        "server": "http://203.0.113.10:8080",
        "username": "testuser",
        "password": "testpass",
    }


@pytest.mark.asyncio
async def test_proxy_without_credentials_omits_username_password():
    browser = FakeBrowser()
    options = ContextOptions(proxy_server="http://203.0.113.10:8080")
    await create_context(browser, options)

    assert browser.last_kwargs["proxy"] == {"server": "http://203.0.113.10:8080"}


@pytest.mark.asyncio
async def test_playwright_failure_raises_context_creation_error():
    browser = FakeBrowser(raise_on_new_context=True)
    options = ContextOptions()
    with pytest.raises(ContextCreationError, match="Failed to create browser context"):
        await create_context(browser, options)