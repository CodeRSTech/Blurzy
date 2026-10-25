"""
Module for handling application distribution paths and Qt application metadata configuration.

See Also:
    - [`Window`][app.ui.qt.window.window.Window] — initializes the main Qt application window
    - [`TransportControlsPanel`][app.ui.qt.sections.transport_controls_panel.TransportControlsPanel] — loads packaged control icons

Layer: Shared utilities.
Context: Provides reusable cross-layer helpers without owning application workflow state.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


APP_NAME = "Blurzy"
APP_VERSION = "1.2.0"
APP_ORGANIZATION_NAME = "CodeRSTech"
_RESOURCE_ROOT_PARTS = ("app", "ui", "qt", "resources")


def _distribution_root() -> Path:
    """
    Return the root path of the application's distribution.

    Returns:
        Root path used to locate bundled resources.
    """
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return Path(__file__).resolve().parents[2]


def bundled_resource_path(*relative_parts: str) -> Path:
    """
    Return the absolute path to a bundled application resource.

    Args:
        *relative_parts: Path components appended beneath the resource root.

    Returns:
        Absolute path to the requested resource.
    """
    return _distribution_root().joinpath(*_RESOURCE_ROOT_PARTS, *relative_parts)


def configure_qt_application_metadata(q_app: QApplication) -> None:
    """
    Set the Qt application name, version, organization, and optional icon.

    Args:
        q_app: Qt application instance to configure.
    """
    from PySide6.QtGui import QIcon

    q_app.setApplicationName(APP_NAME)
    q_app.setApplicationDisplayName(APP_NAME)
    q_app.setApplicationVersion(APP_VERSION)
    q_app.setOrganizationName(APP_ORGANIZATION_NAME)

    icon_path = bundled_resource_path("icon.ico")
    if icon_path.exists():
        q_app.setWindowIcon(QIcon(str(icon_path)))
