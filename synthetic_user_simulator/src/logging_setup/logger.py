"""Logging setup: human-readable console output + JSON Lines session log.

Named `logging_setup` (not `logging`) specifically to avoid shadowing
Python's stdlib `logging` module on import -- see README.md Section 6.

Two separate concerns live here, deliberately kept apart:

  1. `configure_console_logging()` -- a standard library `logging.Logger`
     for free-form operational events (session started, navigation
     started, etc.), formatted per README.md Section 17.
  2. `JsonlSessionLogger` -- writes one structured JSON object per
     *completed* SessionResult to a `.jsonl` file, for later analysis.
     This is intentionally not routed through stdlib `logging` handlers,
     since SessionResult is structured data, not a log message string.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from src.models.session import SessionResult

APP_LOGGER_NAME = "synthetic_user_simulator"

# Defense-in-depth: if a caller ever accidentally passes an unmasked
# proxy identifier (e.g. "http://user:pass@host:port") into a log field,
# mask it here too rather than relying solely on callers having already
# masked it (proxy/manager.py's ProxyEntry.masked is the primary
# mechanism -- this is a second line of defense, not a replacement).
_CREDENTIAL_PATTERN = re.compile(r"://([^:@/]+):([^:@/]+)@")


def _mask_credentials(text: Optional[str]) -> Optional[str]:
    """Replace 'user:pass@' with 'user:****@' in a string, if present."""
    if text is None:
        return None
    return _CREDENTIAL_PATTERN.sub(lambda m: f"://{m.group(1)}:****@", text)


def configure_console_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure and return the application's console logger.

    Idempotent: calling this more than once (e.g. in tests) does not
    stack up duplicate handlers on the logger.

    Args:
        log_level: One of DEBUG/INFO/WARNING/ERROR/CRITICAL (validated
            already by AppConfig.validate() before this is called, but
            defended again here since this function can be used
            standalone, e.g. in tests).

    Returns:
        The configured Logger instance. Callers elsewhere in the project
        should use `logging.getLogger(APP_LOGGER_NAME)` to get the same
        logger rather than reconfiguring it.

    Raises:
        ValueError: if log_level is not a recognized level name.
    """
    level_value = getattr(logging, log_level.upper(), None)
    if not isinstance(level_value, int):
        raise ValueError(f"Unrecognized log_level: {log_level!r}")

    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(level_value)
    # Deliberately left at the default (propagate=True). Setting this to
    # False would stop records from reaching the root logger, which
    # breaks any tooling that listens there -- including pytest's
    # `caplog` fixture (this caused two failing tests when it was False;
    # see tests/unit/test_logger.py). Propagation to a handler-less root
    # logger (the normal case when nothing has called
    # logging.basicConfig()) is a no-op, so this has no practical effect
    # on real console output -- our own StreamHandler below still prints
    # exactly once.

    # Avoid duplicate handlers if this is called more than once.
    logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.StreamHandler)]

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level_value)
    # Matches the format shown in README.md Section 17, e.g.:
    #   [2026-08-19 11:30:15] [INFO] session=0001 event=session_started
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_event(
    logger: logging.Logger,
    level: str,
    event: str,
    session_id: Optional[str] = None,
    **fields: object,
) -> None:
    """Log one operational event in the 'session=... event=...' style.

    Args:
        logger: Logger returned by configure_console_logging().
        level: DEBUG/INFO/WARNING/ERROR/CRITICAL.
        event: Short event name, e.g. "session_started", "navigation_failed".
        session_id: Session this event relates to, if any.
        **fields: Additional key=value fields to append to the message.
            Any field whose value looks like it contains embedded
            credentials (user:pass@host) is masked before formatting.
    """
    parts = []
    if session_id is not None:
        parts.append(f"session={session_id}")
    parts.append(f"event={event}")
    for key, value in fields.items():
        safe_value = _mask_credentials(str(value)) if value is not None else value
        parts.append(f"{key}={safe_value}")

    message = " ".join(parts)
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message)


class JsonlSessionLogger:
    """Writes one JSON object per completed session to a .jsonl file.

    Usage:
        session_logger = JsonlSessionLogger(log_dir=Path("logs"))
        ... run a session, produce a SessionResult ...
        session_logger.write(result)
        session_logger.close()

    Or as a context manager:
        with JsonlSessionLogger(log_dir=Path("logs")) as session_logger:
            session_logger.write(result)
    """

    def __init__(self, log_dir: Union[str, Path], run_id: Optional[str] = None) -> None:
        """
        Args:
            log_dir: Directory the .jsonl file is written into. Created
                if it does not already exist.
            run_id: Identifier used in the filename. Defaults to a
                UTC timestamp so each run gets its own file.

        Raises:
            OSError: if log_dir cannot be created (e.g. permissions).
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.file_path = self.log_dir / f"run_{self.run_id}.jsonl"
        self._file = self.file_path.open("a", encoding="utf-8")

    def write(self, result: SessionResult) -> None:
        """Serialize one SessionResult as a JSON line and flush immediately.

        Args:
            result: A SessionResult, expected to already be in a
                terminal state (mark_complete() called), though this
                does not enforce that -- an in-progress result can be
                written too if a caller wants a mid-run snapshot.
        """
        record = asdict(result)
        record["status"] = result.status.value  # Enum -> plain string for JSON
        record["start_time"] = result.start_time.isoformat()
        record["end_time"] = result.end_time.isoformat() if result.end_time else None
        record["proxy_identifier"] = _mask_credentials(record.get("proxy_identifier"))

        self._file.write(json.dumps(record) + "\n")
        self._file.flush()

    def close(self) -> None:
        """Close the underlying file handle. Safe to call multiple times."""
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "JsonlSessionLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()