"""Unit tests for src/config/loader.py -- load_config()."""

from pathlib import Path

import pytest

from src.config.loader import load_config
from src.config.schema import ConfigError

VALID_YAML = """
platform: dnl
target_url: "https://staging.example.internal/watch/test"
num_sessions: 3
headless: true
"""

MINIMAL_YAML = """
platform: youtube
target_url: "https://www.youtube.com/watch?v=example"
"""


def write_config(tmp_path: Path, content: str) -> Path:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(content, encoding="utf-8")
    return config_file


def test_load_valid_config(tmp_path: Path):
    config_file = write_config(tmp_path, VALID_YAML)
    config = load_config(config_file)
    assert config.platform == "dnl"
    assert config.num_sessions == 3
    assert config.headless is True


def test_load_minimal_config_uses_defaults(tmp_path: Path):
    config_file = write_config(tmp_path, MINIMAL_YAML)
    config = load_config(config_file)
    assert config.platform == "youtube"
    assert config.num_sessions == 1  # default from AppConfig
    assert config.log_level == "INFO"  # default from AppConfig


def test_missing_file_raises_config_error(tmp_path: Path):
    missing_path = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ConfigError, match="not found"):
        load_config(missing_path)


def test_empty_file_raises_config_error(tmp_path: Path):
    config_file = write_config(tmp_path, "")
    with pytest.raises(ConfigError, match="empty"):
        load_config(config_file)


def test_non_mapping_yaml_raises_config_error(tmp_path: Path):
    config_file = write_config(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(config_file)


def test_invalid_yaml_syntax_raises_config_error(tmp_path: Path):
    config_file = write_config(tmp_path, "platform: [unclosed\n")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(config_file)


def test_unknown_key_raises_config_error(tmp_path: Path):
    content = MINIMAL_YAML + "\nnot_a_real_field: true\n"
    config_file = write_config(tmp_path, content)
    with pytest.raises(ConfigError, match="unknown keys"):
        load_config(config_file)


def test_missing_required_field_raises_config_error(tmp_path: Path):
    config_file = write_config(tmp_path, "platform: dnl\n")  # no target_url
    with pytest.raises(ConfigError, match="missing required fields"):
        load_config(config_file)


def test_semantically_invalid_config_raises_config_error(tmp_path: Path):
    content = MINIMAL_YAML + "\nnum_sessions: 0\n"
    config_file = write_config(tmp_path, content)
    with pytest.raises(ConfigError, match="num_sessions"):
        load_config(config_file)