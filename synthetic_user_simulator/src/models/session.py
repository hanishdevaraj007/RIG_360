"""Data models representing a single synthetic session and its outcome.

These are plain data containers with no behavior of their own. Anything
that *does* something (opens a browser, navigates, sends chat) lives in
later modules (browser/, platforms/, chat/) and produces or consumes these
types rather than being mixed into them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SessionStatus(str, Enum):
    """Terminal status of a session, used for logging and summaries.

    SUCCESS  -- session completed its planned lifecycle without error.
    PARTIAL  -- session completed but at least one sub-step failed
                (e.g. chat send failed, but watch/navigation succeeded).
    FAILED   -- session could not complete its core purpose
                (e.g. navigation failed, browser crashed).
    """

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SessionConfig:
    """Per-session runtime parameters, derived from AppConfig at dispatch time.

    One SessionConfig is built per session by the orchestrator (not yet
    implemented). It is intentionally flat and immutable (frozen) so a
    session's parameters cannot be mutated after it starts, which would
    make logs misleading.
    """

    session_id: str
    platform: str
    target_url: str
    watch_duration_seconds: float
    start_delay_seconds: float
    proxy_identifier: Optional[str] = None
    chat_enabled: bool = False
    planned_chat_message_count: int = 0
    headless: bool = True


@dataclass
class SessionResult:
    """Outcome record for a completed (or failed) session.

    This is the object that gets serialized to the JSON Lines log file by
    logging_setup/logger.py (not yet implemented). Fields are populated
    incrementally as the session progresses; `status` and `end_time` are
    only set once the session reaches a terminal state.
    """

    session_id: str
    platform: str
    target_url: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: SessionStatus = SessionStatus.FAILED
    proxy_identifier: Optional[str] = None
    user_agent: Optional[str] = None
    actual_watch_duration_seconds: Optional[float] = None
    chat_messages_sent: int = 0
    error_message: Optional[str] = None

    def mark_complete(
        self,
        status: SessionStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Finalize this result: set end_time and terminal status.

        Args:
            status: Final SessionStatus for this session.
            error_message: Human-readable error detail, if any. Should be
                None for SUCCESS; may be set for PARTIAL or FAILED.
        """
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        self.error_message = error_message

    @property
    def duration_seconds(self) -> Optional[float]:
        """Wall-clock duration from start_time to end_time, if finished."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()


def new_result(config: SessionConfig) -> SessionResult:
    """Build an initial, in-progress SessionResult from a SessionConfig.

    Args:
        config: The SessionConfig this result corresponds to.

    Returns:
        A SessionResult with start_time set to now and status defaulted
        to FAILED (overwritten via mark_complete() once the session
        actually finishes; this default ensures a session that crashes
        before reaching any completion code is still logged as FAILED
        rather than silently missing a status).
    """
    return SessionResult(
        session_id=config.session_id,
        platform=config.platform,
        target_url=config.target_url,
        start_time=datetime.now(timezone.utc),
        proxy_identifier=config.proxy_identifier,
    )