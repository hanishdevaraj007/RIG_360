"""Unit tests for src/platforms/dnl.py."""

import pytest

from src.platforms.base import PlatformError
from src.platforms.dnl import DNLAdapter


@pytest.mark.asyncio
async def test_dnl_adapter_open_stream_raises_platform_error():
    adapter = DNLAdapter()
    assert adapter.platform_name == "dnl"
    with pytest.raises(PlatformError, match="not implemented"):
        await adapter.open_stream(page=object(), target_url="https://dnl.example/watch/x")


@pytest.mark.asyncio
async def test_dnl_adapter_open_stream_error_references_readme_section():
    adapter = DNLAdapter()
    with pytest.raises(PlatformError, match="README.md Section 23"):
        await adapter.open_stream(page=object(), target_url="https://dnl.example/watch/x")


@pytest.mark.asyncio
async def test_dnl_adapter_observe_playback_raises_platform_error():
    adapter = DNLAdapter()
    with pytest.raises(PlatformError, match="not implemented"):
        await adapter.observe_playback(page=object())


@pytest.mark.asyncio
async def test_dnl_adapter_close_is_a_noop():
    adapter = DNLAdapter()
    result = await adapter.close(page=object())
    assert result is None