"""Session orchestration.

This is where every previously-built module comes together: config ->
randomized per-session parameters -> browser/context -> platform adapter
-> behavior engine -> proxy (DNL only) -> logging. It is the last
"backbone" module -- chat sending is deliberately NOT wired in here yet
(chat/ package doesn't exist; DNLAdapter doesn't exist), so this runner
currently only supports platform: youtube end-to-end. Running with
platform: dnl fails fast and clearly via UnsupportedPlatformError rather
than silently doing nothing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from playwright.async_api import Browser

from src.behavior.scheduler import run_watch_behavior
from src.browser.context import ContextCreationError, ContextOptions, create_context
from src.browser.manager import BrowserManager
from src.chat.base import ChatClient, ChatError
from src.chat.dnl_chat import DNLChatClient
from src.chat.message_bank import MessageBank
from src.config.schema import AppConfig
from src.logging_setup.logger import JsonlSessionLogger, log_event
from src.models.session import SessionConfig, SessionResult, SessionStatus, new_result
from src.platforms.base import PlatformAdapter, PlatformError
from src.platforms.dnl import DNLAdapter
from src.platforms.youtube import YouTubeAdapter
from src.proxy.manager import ProxyEntry, ProxyError, ProxyManager, parse_proxy_file
from src.utils.randomization import Randomizer


class UnsupportedPlatformError(Exception):
    """Raised when no adapter/chat client is available for a platform."""


def get_adapter(platform: str) -> PlatformAdapter:
    """Return the PlatformAdapter for the given platform name.

    Args:
        platform: 'dnl' or 'youtube' (already validated by AppConfig).

    Returns:
        A PlatformAdapter instance. For 'dnl' this is DNLAdapter, which
        is a non-functional stub -- every one of its methods raises
        PlatformError with a message pointing to README.md Section 23
        (DNL Integration Points), rather than this factory guessing at
        DNL's real behavior. That error is caught by run_one_session's
        normal PlatformError handling, so a dnl-platform run still fails
        cleanly with a clear, informative FAILED SessionResult instead
        of crashing.

    Raises:
        UnsupportedPlatformError: for any platform name other than
            'dnl'/'youtube'.
    """
    if platform == "youtube":
        return YouTubeAdapter()
    if platform == "dnl":
        return DNLAdapter()
    raise UnsupportedPlatformError(f"No adapter available for platform '{platform}'")


def get_chat_client(platform: str) -> ChatClient:
    """Return the ChatClient for the given platform name.

    Args:
        platform: Platform name. Only 'dnl' has a ChatClient at all --
            chat is not supported for YouTube (README.md Section 4),
            and AppConfig.validate() already prevents chat_enabled=True
            with platform='youtube', so this should only ever be called
            for 'dnl' in practice.

    Returns:
        A ChatClient instance. For 'dnl' this is DNLChatClient, a
        non-functional stub -- see its module docstring and README.md
        Section 23.

    Raises:
        UnsupportedPlatformError: for any platform other than 'dnl'.
    """
    if platform == "dnl":
        return DNLChatClient()
    raise UnsupportedPlatformError(
        f"No chat client available for platform '{platform}' "
        f"(chat is only supported for DNL, see README.md Section 4)"
    )


def build_session_configs(
    config: AppConfig, randomizer: Randomizer
) -> List[SessionConfig]:
    """Build one SessionConfig per planned session, with randomized timing.

    Start delays are spread evenly across `ramp_up_seconds` (so sessions
    don't all start at once), each with additional random jitter from
    `min_session_delay`/`max_session_delay`. Watch duration is randomized
    independently per session within the configured bounds.

    Args:
        config: Validated AppConfig.
        randomizer: Source of randomization. Uses the same instance for
            all sessions' *scheduling* parameters (start delay, watch
            duration) -- each session's *in-behavior* randomization
            later uses its own derived Randomizer (see
            Randomizer.child()), so concurrent sessions don't share RNG
            state during execution.

    Returns:
        List of SessionConfig, one per config.num_sessions, session_id
        zero-padded ("0001", "0002", ...).
    """
    sessions: List[SessionConfig] = []
    for i in range(config.num_sessions):
        session_id = f"{i + 1:04d}"

        if config.num_sessions > 1 and config.ramp_up_seconds > 0:
            base_offset = (config.ramp_up_seconds / (config.num_sessions - 1)) * i
        else:
            base_offset = 0.0
        jitter = randomizer.uniform_float(
            config.min_session_delay, config.max_session_delay
        )

        watch_duration = randomizer.uniform_float(
            config.min_watch_duration, config.max_watch_duration
        )

        planned_chat_count = (
            randomizer.uniform_int(config.min_chat_messages, config.max_chat_messages)
            if config.chat_enabled
            else 0
        )

        sessions.append(
            SessionConfig(
                session_id=session_id,
                platform=config.platform,
                target_url=config.target_url,
                watch_duration_seconds=watch_duration,
                start_delay_seconds=base_offset + jitter,
                chat_enabled=config.chat_enabled,
                planned_chat_message_count=planned_chat_count,
                min_chat_interval_seconds=config.min_chat_interval,
                max_chat_interval_seconds=config.max_chat_interval,
                headless=config.headless,
            )
        )
    return sessions


async def _send_chat_messages(
    session_config: SessionConfig,
    page,
    console_logger: logging.Logger,
    randomizer: Randomizer,
    result: SessionResult,
) -> Optional[str]:
    """Send this session's planned chat messages, stopping at the first failure.

    Chat failure is treated as a *partial* problem, not a fatal one: the
    watch/playback portion of the session already succeeded by the time
    this is called, so a chat failure downgrades the session to PARTIAL
    rather than FAILED (see run_one_session's status logic).

    Args:
        session_config: This session's parameters, including
            planned_chat_message_count and chat interval bounds.
        page: The session's Page.
        console_logger: Logger for lifecycle events.
        randomizer: This session's Randomizer.
        result: This session's SessionResult, updated in place --
            chat_messages_sent is incremented for each message actually
            sent before any failure.

    Returns:
        None if all planned messages were sent successfully, or an
        error message string describing the first failure encountered
        (chat sending stops at that point rather than retrying
        indefinitely).
    """
    try:
        chat_client = get_chat_client(session_config.platform)
    except UnsupportedPlatformError as exc:
        log_event(
            console_logger,
            "error",
            "chat_unavailable",
            session_id=session_config.session_id,
            error=str(exc),
        )
        return str(exc)

    message_bank = MessageBank()

    for _ in range(session_config.planned_chat_message_count):
        message = message_bank.random_message(randomizer)
        try:
            await chat_client.send_message(page, message)
        except ChatError as exc:
            log_event(
                console_logger,
                "error",
                "chat_message_failed",
                session_id=session_config.session_id,
                error=str(exc),
            )
            return str(exc)

        result.chat_messages_sent += 1
        log_event(
            console_logger,
            "info",
            "chat_message_sent",
            session_id=session_config.session_id,
            count=result.chat_messages_sent,
        )

        interval = randomizer.uniform_float(
            session_config.min_chat_interval_seconds,
            session_config.max_chat_interval_seconds,
        )
        await asyncio.sleep(interval)

    return None


async def run_one_session(
    session_config: SessionConfig,
    browser: Browser,
    proxy_manager: Optional[ProxyManager],
    console_logger: logging.Logger,
    randomizer: Randomizer,
    semaphore: asyncio.Semaphore,
) -> SessionResult:
    """Run a single session end-to-end: context -> adapter -> behavior -> cleanup.

    Errors from known failure categories (PlatformError, proxy/context
    creation errors, unsupported platform) are caught and turned into a
    FAILED SessionResult -- they do not propagate, so one session's
    failure never affects sibling sessions (README.md Section 18).
    Cancellation (asyncio.CancelledError, e.g. Ctrl+C shutdown) is
    intentionally NOT caught here: cleanup still runs via `finally`, but
    the cancellation itself propagates to the caller, which is
    responsible for turning it into a final result (see Orchestrator.run).

    Args:
        session_config: This session's parameters.
        browser: Shared Browser instance (one browser hosts many
            concurrent contexts).
        proxy_manager: If set, used to assign/report proxy success or
            failure for this session (DNL only -- always None for
            YouTube sessions, enforced already by AppConfig.validate()).
        console_logger: Logger for lifecycle events.
        randomizer: This session's own derived Randomizer.
        semaphore: Concurrency cap shared across all sessions in the run.

    Returns:
        A terminal SessionResult (SUCCESS, PARTIAL, or FAILED).
    """
    result = new_result(session_config)
    context = None
    proxy_entry: Optional[ProxyEntry] = None

    async with semaphore:
        await asyncio.sleep(session_config.start_delay_seconds)
        log_event(
            console_logger,
            "info",
            "session_started",
            session_id=session_config.session_id,
            platform=session_config.platform,
        )
        try:
            if proxy_manager is not None:
                proxy_entry = proxy_manager.assign()
                result.proxy_identifier = proxy_entry.masked
                log_event(
                    console_logger,
                    "info",
                    "proxy_assigned",
                    session_id=session_config.session_id,
                    proxy=proxy_entry.masked,
                )

            context_options = ContextOptions(
                proxy_server=proxy_entry.server if proxy_entry else None,
                proxy_username=proxy_entry.username if proxy_entry else None,
                proxy_password=proxy_entry.password if proxy_entry else None,
            )
            context = await create_context(browser, context_options)
            page = await context.new_page()

            adapter = get_adapter(session_config.platform)

            log_event(
                console_logger,
                "info",
                "navigation_started",
                session_id=session_config.session_id,
                url=session_config.target_url,
            )
            await adapter.open_stream(page, session_config.target_url)

            observation = await adapter.observe_playback(page)
            log_event(
                console_logger,
                "info",
                "playback_observed",
                session_id=session_config.session_id,
                page_loaded=observation.page_loaded,
                playback_started=observation.playback_started,
            )

            await run_watch_behavior(page, randomizer, session_config.watch_duration_seconds)
            result.actual_watch_duration_seconds = session_config.watch_duration_seconds

            chat_error_message: Optional[str] = None
            if session_config.chat_enabled and session_config.planned_chat_message_count > 0:
                chat_error_message = await _send_chat_messages(
                    session_config, page, console_logger, randomizer, result
                )

            await adapter.close(page)

            if proxy_entry is not None and proxy_manager is not None:
                proxy_manager.mark_success(proxy_entry)

            if not observation.page_loaded:
                result.mark_complete(
                    SessionStatus.PARTIAL,
                    error_message=f"page did not appear to load: {observation.detail}",
                )
            elif chat_error_message is not None:
                result.mark_complete(SessionStatus.PARTIAL, error_message=chat_error_message)
            else:
                result.mark_complete(SessionStatus.SUCCESS)

        except (PlatformError, ContextCreationError, ProxyError, UnsupportedPlatformError) as exc:
            if proxy_entry is not None and proxy_manager is not None:
                proxy_manager.mark_failure(proxy_entry)
            log_event(
                console_logger,
                "error",
                "session_failed",
                session_id=session_config.session_id,
                error=str(exc),
            )
            result.mark_complete(SessionStatus.FAILED, error_message=str(exc))

        except asyncio.CancelledError:
            log_event(
                console_logger,
                "warning",
                "session_cancelled",
                session_id=session_config.session_id,
            )
            raise  # deliberately not swallowed -- see docstring

        except Exception as exc:  # noqa: BLE001 -- last-resort boundary, always logged
            log_event(
                console_logger,
                "error",
                "session_unexpected_error",
                session_id=session_config.session_id,
                error=str(exc),
            )
            result.mark_complete(
                SessionStatus.FAILED, error_message=f"unexpected error: {exc}"
            )

        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception as exc:  # noqa: BLE001 -- cleanup must not raise
                    log_event(
                        console_logger,
                        "warning",
                        "context_close_failed",
                        session_id=session_config.session_id,
                        error=str(exc),
                    )
            log_event(
                console_logger,
                "info",
                "session_ended",
                session_id=session_config.session_id,
                status=result.status.value,
            )

    return result


class Orchestrator:
    """Runs a full set of concurrent sessions for one AppConfig."""

    def __init__(
        self,
        config: AppConfig,
        console_logger: logging.Logger,
        session_logger: JsonlSessionLogger,
    ) -> None:
        """
        Args:
            config: Validated AppConfig for this run.
            console_logger: Logger for lifecycle events.
            session_logger: Writer for per-session JSONL records.
        """
        self.config = config
        self.console_logger = console_logger
        self.session_logger = session_logger
        self.randomizer = Randomizer(seed=config.random_seed)

    def _build_proxy_manager(self) -> Optional[ProxyManager]:
        """Parse and build a ProxyManager if proxies are enabled, else None.

        Raises:
            ProxyError: if use_proxies is True but the proxy file is
                missing, empty, or malformed. Raised before any browser
                is launched, so a bad proxy file fails fast.
        """
        if not self.config.use_proxies:
            return None
        proxies = parse_proxy_file(self.config.proxy_file_path)
        return ProxyManager(proxies, max_retry_attempts=self.config.proxy_retry_attempts)

    def _collect_results(
        self,
        session_configs: List[SessionConfig],
        outcomes: List[object],
    ) -> List[SessionResult]:
        """Turn asyncio.gather(..., return_exceptions=True) outcomes into SessionResults.

        A session normally returns its own SessionResult. If a session's
        task instead surfaces an exception (this should be rare, since
        run_one_session catches its own errors -- the main case is
        CancelledError during shutdown), a synthetic FAILED result is
        built here so the run summary always accounts for every planned
        session.
        """
        results: List[SessionResult] = []
        for session_config, outcome in zip(session_configs, outcomes):
            if isinstance(outcome, SessionResult):
                results.append(outcome)
                continue
            fallback = new_result(session_config)
            if isinstance(outcome, asyncio.CancelledError):
                reason = "cancelled during shutdown"
            else:
                reason = f"session task raised an unhandled error: {outcome}"
            fallback.mark_complete(SessionStatus.FAILED, error_message=reason)
            results.append(fallback)
        return results

    async def run(self) -> List[SessionResult]:
        """Run all configured sessions and return their results.

        Sessions run concurrently, capped by
        `config.max_concurrent_browsers` via an asyncio.Semaphore. If
        cancelled (e.g. Ctrl+C, per README.md Section 28), remaining
        session tasks are cancelled, given a chance to clean up their
        browser contexts, and reported as FAILED("cancelled during
        shutdown") rather than silently dropped -- then the
        CancelledError is re-raised so the caller (main.py) knows the
        run did not complete normally.

        Returns:
            One SessionResult per planned session, in session order.

        Raises:
            ProxyError: if proxy configuration is invalid (raised before
                any browser is launched).
            BrowserLaunchError: if the browser fails to start.
            asyncio.CancelledError: if the run is cancelled; results
                gathered up to that point are still written to the
                session log before this is re-raised.
        """
        proxy_manager = self._build_proxy_manager()
        session_configs = build_session_configs(self.config, self.randomizer)
        semaphore = asyncio.Semaphore(self.config.max_concurrent_browsers)

        async with BrowserManager(headless=self.config.headless) as browser:
            tasks = [
                asyncio.ensure_future(
                    run_one_session(
                        session_config,
                        browser,
                        proxy_manager,
                        self.console_logger,
                        self.randomizer.child(),
                        semaphore,
                    )
                )
                for session_config in session_configs
            ]

            try:
                outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                log_event(
                    self.console_logger,
                    "warning",
                    "run_cancelled",
                    reason="shutdown requested, cancelling remaining sessions",
                )
                for task in tasks:
                    task.cancel()
                outcomes = await asyncio.gather(*tasks, return_exceptions=True)
                results = self._collect_results(session_configs, outcomes)
                for result in results:
                    self.session_logger.write(result)
                raise

        results = self._collect_results(session_configs, outcomes)
        for result in results:
            self.session_logger.write(result)
        return results