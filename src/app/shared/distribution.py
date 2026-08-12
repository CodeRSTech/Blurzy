from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


APP_NAME = "Blurzy"
APP_VERSION = "0.1.0"
APP_ORGANIZATION_NAME = "CodeRSTech"
_RESOURCE_ROOT_PARTS = ("app", "ui", "qt", "resources")


def _distribution_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return Path(__file__).resolve().parents[2]


def bundled_resource_path(*relative_parts: str) -> Path:
    return _distribution_root().joinpath(*_RESOURCE_ROOT_PARTS, *relative_parts)


def configure_qt_application_metadata(q_app: QApplication) -> None:
    q_app.setApplicationName(APP_NAME)
    q_app.setApplicationDisplayName(APP_NAME)
    q_app.setApplicationVersion(APP_VERSION)
    q_app.setOrganizationName(APP_ORGANIZATION_NAME)
