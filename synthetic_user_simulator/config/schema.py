"""Typed application configuration and its validation rules.

AppConfig is the single source of truth for all tunable behavior in this
project (see README.md Section 13 for the parameter reference). Nothing
elsewhere in the codebase should read raw YAML/dict config directly --
everything should receive an already-validated AppConfig instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or inconsistent.

    Distinct from browser/navigation/proxy errors (defined in their own
    modules later) so failures can be told apart at a glance in logs.
    """


SUPPORTED_PLATFORMS = ("dnl", "youtube")


@dataclass
class AppConfig:
    """Validated, typed application configuration.

    Field meanings correspond 1:1 to README.md Section 13. Defaults here
    are conservative (small session counts, headless off is NOT default --
    headless True is default) so an accidental run doesn't do anything
    large by surprise.
    """

    platform: str
    target_url: str

    num_sessions: int = 1
    max_concurrent_browsers: int = 5

    ramp_up_seconds: float = 0.0
    min_session_delay: float = 0.0
    max_session_delay: float = 0.0

    min_watch_duration: float = 10.0
    max_watch_duration: float = 30.0

    use_proxies: bool = False
    proxy_file_path: Optional[str] = None
    proxy_retry_attempts: int = 1

    chat_enabled: bool = False
    min_chat_messages: int = 0
    max_chat_messages: int = 0
    min_chat_interval: float = 5.0
    max_chat_interval: float = 15.0

    youtube_quality_preference: Optional[str] = None

    headless: bool = True
    log_level: str = "INFO"
    random_seed: Optional[int] = None

    def validate(self) -> None:
        """Validate this config, raising ConfigError on the first problem found.

        Called explicitly by the loader after construction, rather than
        inside __post_init__, so tests can build an intentionally-invalid
        AppConfig and assert on validate() without dataclass construction
        itself throwing.
        """
        errors: List[str] = []

        if self.platform not in SUPPORTED_PLATFORMS:
            errors.append(
                f"platform must be one of {SUPPORTED_PLATFORMS}, got '{self.platform}'"
            )

        if not self.target_url or not self.target_url.strip():
            errors.append("target_url must be a non-empty string")

        if self.num_sessions < 1:
            errors.append("num_sessions must be >= 1")

        if self.max_concurrent_browsers < 1:
            errors.append("max_concurrent_browsers must be >= 1")

        if self.ramp_up_seconds < 0:
            errors.append("ramp_up_seconds must be >= 0")

        if self.min_session_delay < 0:
            errors.append("min_session_delay must be >= 0")
        if self.max_session_delay < self.min_session_delay:
            errors.append("max_session_delay must be >= min_session_delay")

        if self.min_watch_duration <= 0:
            errors.append("min_watch_duration must be > 0")
        if self.max_watch_duration < self.min_watch_duration:
            errors.append("max_watch_duration must be >= min_watch_duration")

        if self.use_proxies:
            if not self.proxy_file_path or not self.proxy_file_path.strip():
                errors.append("proxy_file_path is required when use_proxies is true")
            if self.platform != "dnl":
                errors.append(
                    "use_proxies is only supported for platform='dnl' "
                    "(see README.md Section 4 -- YouTube scope is "
                    "observation-only and does not use proxies)"
                )
        if self.proxy_retry_attempts < 0:
            errors.append("proxy_retry_attempts must be >= 0")

        if self.chat_enabled and self.platform != "dnl":
            errors.append(
                "chat_enabled is only supported for platform='dnl' "
                "(see README.md Section 4 -- YouTube chat automation "
                "is not implemented)"
            )
        if self.min_chat_messages < 0:
            errors.append("min_chat_messages must be >= 0")
        if self.max_chat_messages < self.min_chat_messages:
            errors.append("max_chat_messages must be >= min_chat_messages")
        if self.chat_enabled and self.min_chat_interval <= 0:
            errors.append("min_chat_interval must be > 0 when chat_enabled is true")
        if self.max_chat_interval < self.min_chat_interval:
            errors.append("max_chat_interval must be >= min_chat_interval")

        valid_log_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if self.log_level.upper() not in valid_log_levels:
            errors.append(f"log_level must be one of {valid_log_levels}")

        if errors:
            raise ConfigError(
                "Invalid configuration:\n  - " + "\n  - ".join(errors)
            )