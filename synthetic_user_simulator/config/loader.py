"""Loads config.yaml into a validated AppConfig.

This module is the only place in the project that should read raw YAML.
Everything downstream receives an AppConfig object, never a dict.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Dict, Union

import yaml

from src.config.schema import AppConfig, ConfigError

# Fields that exist on AppConfig -- used to reject unknown keys in the
# YAML file with a clear error instead of silently ignoring a typo.
_VALID_FIELDS = {f.name for f in dataclasses.fields(AppConfig)}


def load_config(path: Union[str, Path]) -> AppConfig:
    """Load, parse, and validate a YAML config file.

    Args:
        path: Path to a config YAML file (e.g. config/config.yaml).

    Returns:
        A validated AppConfig instance.

    Raises:
        ConfigError: if the file is missing, is not valid YAML, does not
            contain a mapping at the top level, contains unknown keys, is
            missing required fields, or fails AppConfig.validate().
    """
    config_path = Path(path)

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read config file {config_path}: {exc}") from exc

    try:
        data: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config file {config_path} is not valid YAML: {exc}") from exc

    if data is None:
        raise ConfigError(f"Config file {config_path} is empty")

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file {config_path} must contain a YAML mapping "
            f"(key: value pairs) at the top level, got {type(data).__name__}"
        )

    unknown_keys = set(data.keys()) - _VALID_FIELDS
    if unknown_keys:
        raise ConfigError(
            f"Config file {config_path} contains unknown keys: "
            f"{sorted(unknown_keys)}. Valid keys are: {sorted(_VALID_FIELDS)}"
        )

    config = _build_config(data, config_path)
    config.validate()
    return config


def _build_config(data: Dict[str, Any], source: Path) -> AppConfig:
    """Construct an AppConfig from a raw dict, catching missing/bad required fields.

    Args:
        data: Parsed YAML content (already confirmed to be a dict with
            only known keys).
        source: Path the data came from, used for error messages.

    Returns:
        An unvalidated AppConfig (field types as given by YAML; range/
        consistency validation happens separately in AppConfig.validate()).

    Raises:
        ConfigError: if a required field is missing or a value's basic
            type does not match what AppConfig expects.
    """
    try:
        return AppConfig(**data)
    except TypeError as exc:
        # dataclass raises TypeError for missing required args or
        # unexpected keyword args; translate to our own error type so
        # callers only need to catch ConfigError.
        raise ConfigError(
            f"Config file {source} is missing required fields or has "
            f"malformed structure: {exc}"
        ) from exc