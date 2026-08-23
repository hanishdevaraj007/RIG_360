"""Unit tests for src/platforms/base.py.

PlatformAdapter is abstract, so these tests verify (a) it cannot be
instantiated directly, and (b) a minimal concrete subclass satisfies the
interface correctly, using a fake Page rather than a real Playwright Page.
"""

import pytest

from src.platforms.base import PlatformAdapter, PlatformError, PlaybackObservation


class FakePage:
    """Minimal stand-in for playwright.async_api.Page."""

    def __init__(self):
        self.navigated_to = None

    async def goto(self, url: str):
        self.navigated_to = url


class FakeAdapter(PlatformAdapter):
    """Minimal concrete PlatformAdapter used only to test the base contract."""

    platform_name = "fake"

    def __init__(self, fail_open: bool = False):
        self.fail_open = fail_open
        self.closed = False

    async def open_stream(self, page, target_url: str) -> None:
        if self.fail_open:
            raise PlatformError("simulated open failure")
        await page.goto(target_url)

    async def observe_playback(self, page) -> PlaybackObservation:
        loaded = page.navigated_to is not None
        return PlaybackObservation(page_loaded=loaded, playback_started=loaded)

    async def close(self, page) -> None:
        self.closed = True


def test_platform_adapter_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        PlatformAdapter()  # abstract methods not implemented


@pytest.mark.asyncio
async def test_fake_adapter_open_stream_navigates_page():
    adapter = FakeAdapter()
    page = FakePage()
    await adapter.open_stream(page, "https://example.internal/watch/test")
    assert page.navigated_to == "https://example.internal/watch/test"


@pytest.mark.asyncio
async def test_fake_adapter_observe_playback_reflects_actual_state():
    adapter = FakeAdapter()
    page = FakePage()

    before = await adapter.observe_playback(page)
    assert before.page_loaded is False
    assert before.playback_started is False

    await adapter.open_stream(page, "https://example.internal/watch/test")
    after = await adapter.observe_playback(page)
    assert after.page_loaded is True
    assert after.playback_started is True


@pytest.mark.asyncio
async def test_fake_adapter_open_stream_failure_raises_platform_error():
    adapter = FakeAdapter(fail_open=True)
    page = FakePage()
    with pytest.raises(PlatformError, match="simulated open failure"):
        await adapter.open_stream(page, "https://example.internal/watch/test")


@pytest.mark.asyncio
async def test_fake_adapter_close_is_called():
    adapter = FakeAdapter()
    page = FakePage()
    assert adapter.closed is False
    await adapter.close(page)
    assert adapter.closed is True