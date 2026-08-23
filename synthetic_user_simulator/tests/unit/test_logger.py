"""Unit tests for src/logging_setup/logger.py."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.logging_setup.logger import (
    JsonlSessionLogger,
    configure_console_logging,
    log_event,
)
from src.models.session import SessionResult, SessionStatus


def make_result(**overrides) -> SessionResult:
    base = dict(
        session_id="0001",
        platform="dnl",
        target_url="https://staging.example.internal/watch/test",
        start_time=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SessionResult(**base)


# --- configure_console_logging / log_event --------------------------------

def test_configure_console_logging_returns_logger_with_correct_level():
    logger = configure_console_logging("DEBUG")
    assert logger.level == logging.DEBUG


def test_configure_console_logging_rejects_bad_level():
    with pytest.raises(ValueError, match="Unrecognized log_level"):
        configure_console_logging("VERBOSE")


def test_configure_console_logging_is_idempotent_no_duplicate_handlers():
    configure_console_logging("INFO")
    configure_console_logging("INFO")
    logger = configure_console_logging("INFO")
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(stream_handlers) == 1


def test_log_event_formats_message_with_session_and_fields(caplog):
    logger = configure_console_logging("INFO")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(logger, "info", "session_started", session_id="0001", platform="dnl")
    assert "session=0001" in caplog.text
    assert "event=session_started" in caplog.text
    assert "platform=dnl" in caplog.text


def test_log_event_masks_credentials_in_field_values(caplog):
    logger = configure_console_logging("INFO")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(
            logger,
            "info",
            "proxy_assigned",
            session_id="0001",
            proxy="http://testuser:testpass@203.0.113.10:8080",
        )
    assert "testpass" not in caplog.text
    assert "****" in caplog.text


# --- JsonlSessionLogger -----------------------------------------------------

def test_jsonl_logger_writes_one_line_per_session(tmp_path: Path):
    with JsonlSessionLogger(log_dir=tmp_path, run_id="test1") as session_logger:
        r1 = make_result(session_id="0001")
        r1.mark_complete(SessionStatus.SUCCESS)
        session_logger.write(r1)

        r2 = make_result(session_id="0002")
        r2.mark_complete(SessionStatus.FAILED, error_message="navigation timeout")
        session_logger.write(r2)

    log_file = tmp_path / "run_test1.jsonl"
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    record1 = json.loads(lines[0])
    assert record1["session_id"] == "0001"
    assert record1["status"] == "SUCCESS"

    record2 = json.loads(lines[1])
    assert record2["session_id"] == "0002"
    assert record2["status"] == "FAILED"
    assert record2["error_message"] == "navigation timeout"


def test_jsonl_logger_masks_proxy_credentials(tmp_path: Path):
    with JsonlSessionLogger(log_dir=tmp_path, run_id="test2") as session_logger:
        result = make_result(
            proxy_identifier="http://testuser:testpass@203.0.113.10:8080"
        )
        result.mark_complete(SessionStatus.SUCCESS)
        session_logger.write(result)

    log_file = tmp_path / "run_test2.jsonl"
    content = log_file.read_text(encoding="utf-8")
    assert "testpass" not in content
    assert "****" in content


def test_jsonl_logger_creates_log_dir_if_missing(tmp_path: Path):
    nested_dir = tmp_path / "does" / "not" / "exist"
    session_logger = JsonlSessionLogger(log_dir=nested_dir, run_id="test3")
    session_logger.close()
    assert nested_dir.exists()


def test_jsonl_logger_close_is_idempotent(tmp_path: Path):
    session_logger = JsonlSessionLogger(log_dir=tmp_path, run_id="test4")
    session_logger.close()
    session_logger.close()  # should not raise