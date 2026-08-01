from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast, TYPE_CHECKING

from loguru import logger

from app.shared.runtime_config import (
    ENV_LOG_CONSOLE_LEVEL,
    ENV_LOG_FILE_LEVEL,
    ENV_LOG_FILE_PATH,
    normalize_log_level,
    validate_log_file_path,
)

if TYPE_CHECKING:
    from loguru import Logger


def _build_filter(enabled_areas: set[str] | None):
    if enabled_areas is None:
        return lambda record: True

    normalized_areas = {area.strip().lower() for area in enabled_areas}

    def area_filter(record) -> bool:
        area = str(record["extra"].get("area", "")).strip().lower()
        return area in normalized_areas

    return area_filter


def configure_logging(
    *,
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    log_file_path: str = "logs/app.log",
    enabled_areas: set[str] | None = None,
) -> None:
    console_level = normalize_log_level(
        console_level, env_var=ENV_LOG_CONSOLE_LEVEL
    )
    file_level = normalize_log_level(file_level, env_var=ENV_LOG_FILE_LEVEL)
    log_file_path = validate_log_file_path(
        log_file_path, env_var=ENV_LOG_FILE_PATH
    )

    logger.remove()

    area_filter = _build_filter(enabled_areas)

    logger.add(
        sys.stderr,
        level=console_level,
        filter=cast(Any, area_filter),
        colorize=True,
        backtrace=False,
        diagnose=False,
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            #"<cyan>{extra[area]}</cyan> | "
            "<level>{message}</level> | "
            "<white>{name}:{function}:{line}</white>"
        ),
    )

    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path,
        level=file_level,
        filter=cast(Any, area_filter),
        encoding="utf-8",
        backtrace=False,
        diagnose=False,
        rotation="10 MB",
        retention=5,
        format=(
            "{time:MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{extra[area]} | "
            "{message}"
            "{name}:{function}:{line} | "
            "{process.id}:{thread.id}"
        ),
    )


def get_logger(area: str) -> Logger:
    return logger.bind(area=area)
