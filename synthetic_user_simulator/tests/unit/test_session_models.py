"""Unit tests for src/models/session.py."""

from src.models.session import SessionConfig, SessionStatus, new_result


def make_session_config(**overrides) -> SessionConfig:
    base = dict(
        session_id="0001",
        platform="dnl",
        target_url="https://staging.example.internal/watch/test",
        watch_duration_seconds=15.0,
        start_delay_seconds=0.0,
    )
    base.update(overrides)
    return SessionConfig(**base)


def test_new_result_defaults_to_failed_until_marked_complete():
    config = make_session_config()
    result = new_result(config)
    assert result.status == SessionStatus.FAILED
    assert result.end_time is None
    assert result.session_id == "0001"


def test_mark_complete_sets_status_and_end_time():
    config = make_session_config()
    result = new_result(config)
    result.mark_complete(SessionStatus.SUCCESS)
    assert result.status == SessionStatus.SUCCESS
    assert result.end_time is not None
    assert result.duration_seconds is not None
    assert result.duration_seconds >= 0


def test_mark_complete_with_error_message():
    config = make_session_config()
    result = new_result(config)
    result.mark_complete(SessionStatus.FAILED, error_message="navigation timed out")
    assert result.status == SessionStatus.FAILED
    assert result.error_message == "navigation timed out"


def test_duration_seconds_none_before_completion():
    config = make_session_config()
    result = new_result(config)
    assert result.duration_seconds is None


def test_session_config_carries_proxy_and_chat_fields():
    config = make_session_config(
        proxy_identifier="203.0.113.10:8080",
        chat_enabled=True,
        planned_chat_message_count=2,
    )
    assert config.proxy_identifier == "203.0.113.10:8080"
    assert config.chat_enabled is True
    assert config.planned_chat_message_count == 2