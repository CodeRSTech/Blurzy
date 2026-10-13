"""
Module for handling application distribution paths and Qt application metadata configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


APP_NAME = "Blurzy"
APP_VERSION = "1.1.0"
APP_ORGANIZATION_NAME = "CodeRSTech"
_RESOURCE_ROOT_PARTS = ("app", "ui", "qt", "resources")


def _distribution_root() -> Path:
    """
    Get the root path of the application's distribution.
    :return: The root path of the application's distribution.
    """
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return Path(__file__).resolve().parents[2]


def bundled_resource_path(*relative_parts: str) -> Path:
    """
    Get the absolute path to a resource file bundled with the application.
    :param relative_parts: The relative path parts to the resource file.
    :return: The absolute path to the resource file.
    """
    return _distribution_root().joinpath(*_RESOURCE_ROOT_PARTS, *relative_parts)


def configure_qt_application_metadata(q_app: QApplication) -> None:
    """
    Configure the metadata (name, version, organization) for the Qt application.
    :param q_app: The Qt application instance.
    :return: None
    """
    from PySide6.QtGui import QIcon

    q_app.setApplicationName(APP_NAME)
    q_app.setApplicationDisplayName(APP_NAME)
    q_app.setApplicationVersion(APP_VERSION)
    q_app.setOrganizationName(APP_ORGANIZATION_NAME)

    icon_path = bundled_resource_path("icon.ico")
    if icon_path.exists():
        q_app.setWindowIcon(QIcon(str(icon_path)))
