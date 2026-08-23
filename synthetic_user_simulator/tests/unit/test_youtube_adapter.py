"""Unit tests for src/platforms/youtube.py.

Uses fake Page/ElementHandle objects, not a real browser -- these test
YouTubeAdapter's own logic (what it does with page responses), not
Playwright or YouTube itself.
"""

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.platforms.base import PlatformError
from src.platforms.youtube import YouTubeAdapter


class FakeElementHandle:
    def __init__(self, state: dict):
        self._state = state

    async def evaluate(self, script: str):
        return self._state


class FakePage:
    def __init__(
        self,
        title: str = "Test Video - YouTube",
        video_state: dict | None = None,
        goto_raises: Exception | None = None,
        video_selector_timeout: bool = False,
    ):
        self._title = title
        self._video_state = video_state
        self.goto_raises = goto_raises
        self.video_selector_timeout = video_selector_timeout
        self.navigated_to = None

    async def goto(self, url, wait_until=None, timeout=None):
        if self.goto_raises:
            raise self.goto_raises
        self.navigated_to = url

    async def title(self):
        return self._title

    async def wait_for_selector(self, selector, timeout=None):
        if self.video_selector_timeout:
            raise PlaywrightTimeoutError("Timeout waiting for selector")
        return FakeElementHandle(self._video_state or {})


@pytest.mark.asyncio
async def test_open_stream_navigates_page():
    adapter = YouTubeAdapter()
    page = FakePage()
    await adapter.open_stream(page, "https://www.youtube.com/watch?v=example")
    assert page.navigated_to == "https://www.youtube.com/watch?v=example"


@pytest.mark.asyncio
async def test_open_stream_timeout_raises_platform_error():
    adapter = YouTubeAdapter()
    page = FakePage(goto_raises=PlaywrightTimeoutError("Timeout 30000ms exceeded"))
    with pytest.raises(PlatformError, match="timed out"):
        await adapter.open_stream(page, "https://www.youtube.com/watch?v=example")


@pytest.mark.asyncio
async def test_open_stream_generic_failure_raises_platform_error():
    adapter = YouTubeAdapter()
    page = FakePage(goto_raises=RuntimeError("DNS resolution failed"))
    with pytest.raises(PlatformError, match="failed"):
        await adapter.open_stream(page, "https://www.youtube.com/watch?v=example")


@pytest.mark.asyncio
async def test_observe_playback_detects_playing_video():
    adapter = YouTubeAdapter()
    page = FakePage(video_state={"paused": False, "currentTime": 12.5})
    obs = await adapter.observe_playback(page)
    assert obs.page_loaded is True
    assert obs.playback_started is True


@pytest.mark.asyncio
async def test_observe_playback_detects_paused_video_as_not_started():
    adapter = YouTubeAdapter()
    page = FakePage(video_state={"paused": True, "currentTime": 0})
    obs = await adapter.observe_playback(page)
    assert obs.page_loaded is True
    assert obs.playback_started is False


@pytest.mark.asyncio
async def test_observe_playback_no_video_element_reports_not_started_not_error():
    adapter = YouTubeAdapter()
    page = FakePage(video_selector_timeout=True)
    obs = await adapter.observe_playback(page)
    assert obs.playback_started is False
    assert "no <video> element" in obs.detail


@pytest.mark.asyncio
async def test_observe_playback_empty_title_means_not_loaded():
    adapter = YouTubeAdapter()
    page = FakePage(title="", video_state={"paused": False, "currentTime": 1.0})
    obs = await adapter.observe_playback(page)
    assert obs.page_loaded is False


@pytest.mark.asyncio
async def test_close_is_a_noop():
    adapter = YouTubeAdapter()
    page = FakePage()
    result = await adapter.close(page)
    assert result is None