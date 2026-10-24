"""
Module for runtime config; provides reusable helpers across application layers.

See Also:
    - [`configure_logging`][app.shared.logging_cfg.configure_logging] — applies validated log-level configuration

Layer: Shared utilities.
Context: Provides reusable helpers across application layers at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import os
from dataclasses import dataclass
from pathlib import Path
if TYPE_CHECKING:
    from typing import Mapping


DEFAULT_LOG_CONSOLE_LEVEL = "DEBUG"
DEFAULT_LOG_FILE_LEVEL = "TRACE"
DEFAULT_LOG_FILE_PATH = "logs/app.log"

ENV_LOG_CONSOLE_LEVEL = "BLURZY_LOG_CONSOLE_LEVEL"
ENV_LOG_FILE_LEVEL = "BLURZY_LOG_FILE_LEVEL"
ENV_LOG_FILE_PATH = "BLURZY_LOG_FILE_PATH"
ENV_LOG_ENABLED_AREAS = "BLURZY_LOG_ENABLED_AREAS"

VALID_LOG_LEVELS = frozenset(
    {
        "TRACE",
        "DEBUG",
        "INFO",
        "SUCCESS",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }
)


class StartupConfigurationError(ValueError):
    """
    Raised when startup configuration cannot be validated safely.

    Layer: Shared utilities.
    Context: Provides reusable cross-layer behavior without owning workflow state.
    """


def normalize_log_level(value: str, *, env_var: str) -> str:
    """
    Normalize log level.

    Args:
        value: Log-level name to normalize and validate.
        env_var: Environment-variable name used in validation errors.

    Returns:
        The normalized uppercase log-level name.
    """
    normalized = value.strip().upper()
    if not normalized:
        raise StartupConfigurationError(
            f"{env_var} must not be empty. Use one of: {', '.join(sorted(VALID_LOG_LEVELS))}."
        )
    if normalized not in VALID_LOG_LEVELS:
        raise StartupConfigurationError(
            f"{env_var}={value!r} is invalid. Use one of: {', '.join(sorted(VALID_LOG_LEVELS))}."
        )
    return normalized


def validate_log_file_path(value: str, *, env_var: str) -> str:
    """
    Validate log file path.

    Args:
        value: Path string to validate.
        env_var: Environment-variable name used in validation errors.

    Returns:
        The trimmed path string.
    """
    normalized = value.strip()
    if not normalized:
        raise StartupConfigurationError(
            f"{env_var} must not be empty. Set it to a writable file path such as 'logs/app.log'."
        )

    path = Path(normalized)
    if path.exists() and path.is_dir():
        raise StartupConfigurationError(
            f"{env_var}={value!r} points to a directory. Set it to a file path such as 'logs/app.log'."
        )
    return normalized


def parse_enabled_areas(value: str | None) -> tuple[str, ...] | None:
    """
    Parse a comma-separated allow-list into a stable deduplicated tuple.

    Args:
        value: Comma-separated logging-area names, or `None` when unrestricted.

    Returns:
        Deduplicated area names, or `None` when no allow-list is configured.
    """
    if value is None:
        return None

    normalized = [item.strip() for item in value.split(",") if item.strip()]
    if not normalized:
        return None
    return tuple(dict.fromkeys(normalized))


@dataclass(frozen=True, slots=True)
class StartupConfig:
    """
    Represent startup config.

    Attributes:
        console_level: Stored console level value.
        file_level: Stored file level value.
        log_file_path: Stored log file path value.
        enabled_areas: Stored enabled areas value.

    Layer: Shared utilities.
    Context: Provides reusable cross-layer behavior without owning workflow state.
    """
    console_level: str = DEFAULT_LOG_CONSOLE_LEVEL
    file_level: str = DEFAULT_LOG_FILE_LEVEL
    log_file_path: str = DEFAULT_LOG_FILE_PATH
    enabled_areas: tuple[str, ...] | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "StartupConfig":
        """
        Build startup configuration from environment variables.

        Args:
            env: Environment mapping to read, or the process environment when omitted.

        Returns:
            Configuration with normalized log levels, validated file path, and parsed area filter.
        """
        source = os.environ if env is None else env
        console_level = normalize_log_level(
            source.get(ENV_LOG_CONSOLE_LEVEL, DEFAULT_LOG_CONSOLE_LEVEL),
            env_var=ENV_LOG_CONSOLE_LEVEL,
        )
        file_level = normalize_log_level(
            source.get(ENV_LOG_FILE_LEVEL, DEFAULT_LOG_FILE_LEVEL),
            env_var=ENV_LOG_FILE_LEVEL,
        )
        log_file_path = validate_log_file_path(
            source.get(ENV_LOG_FILE_PATH, DEFAULT_LOG_FILE_PATH),
            env_var=ENV_LOG_FILE_PATH,
        )
        enabled_areas = parse_enabled_areas(source.get(ENV_LOG_ENABLED_AREAS))
        return cls(
            console_level=console_level,
            file_level=file_level,
            log_file_path=log_file_path,
            enabled_areas=enabled_areas,
        )

    def enabled_areas_for_logging(self) -> set[str] | None:
        """
        Return the application areas enabled for logging.

        Returns:
            A mutable set copied from the configured tuple, or `None` to allow every area.
        """
        if self.enabled_areas is None:
            return None
        return set(self.enabled_areas)
