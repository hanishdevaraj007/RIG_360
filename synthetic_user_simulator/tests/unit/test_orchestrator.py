"""Unit tests for src/orchestrator/runner.py.

Uses fake Browser/Context/Page objects and monkeypatches create_context/
get_adapter -- no real browser is launched in these tests (that's
verified separately, by hand, against a real browser -- see the stage
delivery notes).
"""

import asyncio

import pytest

from src.config.schema import AppConfig
from src.logging_setup.logger import configure_console_logging
from src.models.session import SessionConfig, SessionStatus
from src.platforms.base import PlaybackObservation, PlatformAdapter, PlatformError
from src.orchestrator import runner as runner_module
from src.orchestrator.runner import (
    UnsupportedPlatformError,
    build_session_configs,
    get_adapter,
    run_one_session,
)
from src.proxy.manager import ProxyEntry, ProxyManager
from src.utils.randomization import Randomizer


# --- get_adapter -------------------------------------------------------

def test_get_adapter_youtube_returns_youtube_adapter():
    adapter = get_adapter("youtube")
    assert adapter.platform_name == "youtube"


def test_get_adapter_dnl_returns_dnl_adapter_stub():
    from src.platforms.dnl import DNLAdapter

    adapter = get_adapter("dnl")
    assert isinstance(adapter, DNLAdapter)
    assert adapter.platform_name == "dnl"


def test_get_adapter_unknown_platform_raises():
    with pytest.raises(UnsupportedPlatformError, match="No adapter available"):
        get_adapter("twitch")


# --- build_session_configs -----------------------------------------------

def make_config(**overrides) -> AppConfig:
    base = dict(platform="youtube", target_url="https://example.com/watch")
    base.update(overrides)
    return AppConfig(**base)


def test_build_session_configs_returns_correct_count():
    config = make_config(num_sessions=5)
    sessions = build_session_configs(config, Randomizer(seed=1))
    assert len(sessions) == 5
    assert [s.session_id for s in sessions] == ["0001", "0002", "0003", "0004", "0005"]


def test_build_session_configs_watch_duration_within_bounds():
    config = make_config(num_sessions=10, min_watch_duration=5, max_watch_duration=15)
    sessions = build_session_configs(config, Randomizer(seed=1))
    for s in sessions:
        assert 5 <= s.watch_duration_seconds <= 15


def test_build_session_configs_ramp_up_spreads_start_delays():
    config = make_config(
        num_sessions=3,
        ramp_up_seconds=10,
        min_session_delay=0,
        max_session_delay=0,  # no jitter, so base offsets are exact
    )
    sessions = build_session_configs(config, Randomizer(seed=1))
    delays = [s.start_delay_seconds for s in sessions]
    assert delays == [0.0, 5.0, 10.0]


def test_build_session_configs_single_session_no_ramp_up_division_error():
    config = make_config(num_sessions=1, ramp_up_seconds=10)
    sessions = build_session_configs(config, Randomizer(seed=1))
    assert len(sessions) == 1
    assert sessions[0].start_delay_seconds == 0.0


def test_build_session_configs_reproducible_with_same_seed():
    config = make_config(num_sessions=4)
    sessions_a = build_session_configs(config, Randomizer(seed=42))
    sessions_b = build_session_configs(config, Randomizer(seed=42))
    durations_a = [s.watch_duration_seconds for s in sessions_a]
    durations_b = [s.watch_duration_seconds for s in sessions_b]
    assert durations_a == durations_b


# --- run_one_session -------------------------------------------------------

class FakePage:
    def __init__(self):
        self.mouse = type("M", (), {"move": staticmethod(lambda x, y: _noop())})()

    async def evaluate(self, script):
        pass


async def _noop():
    return None


class FakeContext:
    def __init__(self, fail_new_page: bool = False):
        self.fail_new_page = fail_new_page
        self.closed = False

    async def new_page(self):
        if self.fail_new_page:
            raise RuntimeError("simulated new_page failure")
        return FakePage()

    async def close(self):
        self.closed = True


class FakeAdapter(PlatformAdapter):
    platform_name = "fake"

    def __init__(self, fail_open: bool = False, page_loaded: bool = True):
        self.fail_open = fail_open
        self.page_loaded = page_loaded
        self.closed = False

    async def open_stream(self, page, target_url):
        if self.fail_open:
            raise PlatformError("simulated navigation failure")

    async def observe_playback(self, page):
        return PlaybackObservation(page_loaded=self.page_loaded, playback_started=self.page_loaded)

    async def close(self, page):
        self.closed = True


def make_session_config(**overrides) -> SessionConfig:
    base = dict(
        session_id="0001",
        platform="youtube",
        target_url="https://example.com/watch",
        watch_duration_seconds=0,  # keep tests fast
        start_delay_seconds=0,
    )
    base.update(overrides)
    return SessionConfig(**base)


@pytest.fixture(autouse=True)
def _no_real_playwright_calls(monkeypatch):
    """Prevent every test in this module from touching real Playwright."""
    async def fake_create_context(browser, options):
        return FakeContext()

    monkeypatch.setattr(runner_module, "create_context", fake_create_context)
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter())


@pytest.mark.asyncio
async def test_run_one_session_success_path(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(page_loaded=True))
    result = await run_one_session(
        make_session_config(),
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert result.status == SessionStatus.SUCCESS
    assert result.error_message is None


@pytest.mark.asyncio
async def test_run_one_session_partial_when_page_not_loaded(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(page_loaded=False))
    result = await run_one_session(
        make_session_config(),
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert result.status == SessionStatus.PARTIAL


@pytest.mark.asyncio
async def test_run_one_session_failed_on_platform_error(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(fail_open=True))
    result = await run_one_session(
        make_session_config(),
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert result.status == SessionStatus.FAILED
    assert "simulated navigation failure" in result.error_message


@pytest.mark.asyncio
async def test_run_one_session_failed_on_unexpected_error(monkeypatch):
    async def fake_create_context(browser, options):
        raise ValueError("totally unexpected")

    monkeypatch.setattr(runner_module, "create_context", fake_create_context)
    result = await run_one_session(
        make_session_config(),
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert result.status == SessionStatus.FAILED
    assert "unexpected error" in result.error_message


@pytest.mark.asyncio
async def test_run_one_session_context_always_closed_even_on_failure(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(fail_open=True))

    created_context = FakeContext()

    async def fake_create_context(browser, options):
        return created_context

    monkeypatch.setattr(runner_module, "create_context", fake_create_context)
    await run_one_session(
        make_session_config(),
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert created_context.closed is True


@pytest.mark.asyncio
async def test_run_one_session_assigns_and_marks_proxy_success(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(page_loaded=True))
    proxy = ProxyEntry(scheme="http", host="10.0.0.1", port=8080)
    proxy_manager = ProxyManager(proxies=[proxy], max_retry_attempts=1)

    result = await run_one_session(
        make_session_config(platform="dnl"),
        browser=object(),
        proxy_manager=proxy_manager,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert result.proxy_identifier == proxy.masked
    assert result.status == SessionStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_one_session_marks_proxy_failure_on_platform_error(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(fail_open=True))
    proxy = ProxyEntry(scheme="http", host="10.0.0.1", port=8080)
    proxy_manager = ProxyManager(proxies=[proxy], max_retry_attempts=0)

    await run_one_session(
        make_session_config(platform="dnl"),
        browser=object(),
        proxy_manager=proxy_manager,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert proxy_manager.available_count == 0  # exhausted after 1 failure with max_retry_attempts=0


# --- chat wiring (using a real DNLAdapter/DNLChatClient shape, but the
# adapter/chat client themselves are faked -- DNLAdapter/DNLChatClient
# are non-functional stubs, see test_dnl_adapter.py / test_chat.py) -----

class FakeChatClientSuccess:
    platform_name = "dnl"

    def __init__(self):
        self.sent = []

    async def send_message(self, page, message):
        self.sent.append(message)


class FakeChatClientFailsOnNth:
    platform_name = "dnl"

    def __init__(self, fail_on: int):
        self.fail_on = fail_on
        self.calls = 0

    async def send_message(self, page, message):
        self.calls += 1
        if self.calls == self.fail_on:
            from src.chat.base import ChatError

            raise ChatError(f"simulated chat failure on message {self.fail_on}")


@pytest.mark.asyncio
async def test_run_one_session_sends_all_planned_chat_messages(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(page_loaded=True))
    fake_chat = FakeChatClientSuccess()
    monkeypatch.setattr(runner_module, "get_chat_client", lambda platform: fake_chat)

    session_config = make_session_config(
        platform="dnl",
        chat_enabled=True,
        planned_chat_message_count=3,
        min_chat_interval_seconds=0.01,
        max_chat_interval_seconds=0.01,
    )
    result = await run_one_session(
        session_config,
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert result.status == SessionStatus.SUCCESS
    assert result.chat_messages_sent == 3
    assert len(fake_chat.sent) == 3


@pytest.mark.asyncio
async def test_run_one_session_chat_failure_marks_partial_not_failed(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(page_loaded=True))
    fake_chat = FakeChatClientFailsOnNth(fail_on=2)
    monkeypatch.setattr(runner_module, "get_chat_client", lambda platform: fake_chat)

    session_config = make_session_config(
        platform="dnl",
        chat_enabled=True,
        planned_chat_message_count=3,
        min_chat_interval_seconds=0.01,
        max_chat_interval_seconds=0.01,
    )
    result = await run_one_session(
        session_config,
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    # Watch/playback succeeded -- only chat partially failed -- so this
    # must be PARTIAL, not FAILED (see run_one_session's status logic).
    assert result.status == SessionStatus.PARTIAL
    assert result.chat_messages_sent == 1  # only the 1st message succeeded
    assert "simulated chat failure" in result.error_message


@pytest.mark.asyncio
async def test_run_one_session_chat_disabled_sends_no_messages(monkeypatch):
    monkeypatch.setattr(runner_module, "get_adapter", lambda platform: FakeAdapter(page_loaded=True))
    fake_chat = FakeChatClientSuccess()
    monkeypatch.setattr(runner_module, "get_chat_client", lambda platform: fake_chat)

    session_config = make_session_config(platform="dnl", chat_enabled=False)
    result = await run_one_session(
        session_config,
        browser=object(),
        proxy_manager=None,
        console_logger=configure_console_logging("WARNING"),
        randomizer=Randomizer(seed=1),
        semaphore=asyncio.Semaphore(5),
    )
    assert result.status == SessionStatus.SUCCESS
    assert result.chat_messages_sent == 0
    assert fake_chat.sent == []