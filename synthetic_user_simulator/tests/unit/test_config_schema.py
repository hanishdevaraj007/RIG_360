"""Unit tests for src/config/schema.py -- AppConfig.validate()."""

import pytest

from src.config.schema import AppConfig, ConfigError


def make_valid_config(**overrides) -> AppConfig:
    """Build a minimal valid AppConfig, with optional field overrides."""
    base = dict(
        platform="dnl",
        target_url="https://staging.example.internal/watch/test",
    )
    base.update(overrides)
    return AppConfig(**base)


def test_minimal_valid_config_passes():
    config = make_valid_config()
    config.validate()  # should not raise


def test_unsupported_platform_rejected():
    config = make_valid_config(platform="twitch")
    with pytest.raises(ConfigError, match="platform must be one of"):
        config.validate()


def test_empty_target_url_rejected():
    config = make_valid_config(target_url="   ")
    with pytest.raises(ConfigError, match="target_url"):
        config.validate()


def test_num_sessions_must_be_positive():
    config = make_valid_config(num_sessions=0)
    with pytest.raises(ConfigError, match="num_sessions"):
        config.validate()


def test_max_watch_duration_below_min_rejected():
    config = make_valid_config(min_watch_duration=30, max_watch_duration=10)
    with pytest.raises(ConfigError, match="max_watch_duration"):
        config.validate()


def test_proxies_require_proxy_file_path():
    config = make_valid_config(use_proxies=True, proxy_file_path=None)
    with pytest.raises(ConfigError, match="proxy_file_path is required"):
        config.validate()


def test_proxies_not_allowed_on_youtube():
    config = make_valid_config(
        platform="youtube",
        use_proxies=True,
        proxy_file_path="config/proxies.example.txt",
    )
    with pytest.raises(ConfigError, match="only supported for platform='dnl'"):
        config.validate()


def test_chat_not_allowed_on_youtube():
    config = make_valid_config(platform="youtube", chat_enabled=True)
    with pytest.raises(ConfigError, match="YouTube chat automation"):
        config.validate()


def test_chat_message_bounds_validated():
    config = make_valid_config(
        chat_enabled=True,
        min_chat_messages=5,
        max_chat_messages=2,
    )
    with pytest.raises(ConfigError, match="max_chat_messages"):
        config.validate()


def test_invalid_log_level_rejected():
    config = make_valid_config(log_level="VERBOSE")
    with pytest.raises(ConfigError, match="log_level"):
        config.validate()


def test_multiple_errors_all_reported_together():
    config = make_valid_config(platform="bogus", num_sessions=-1)
    with pytest.raises(ConfigError) as exc_info:
        config.validate()
    message = str(exc_info.value)
    assert "platform must be one of" in message
    assert "num_sessions" in message