from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import app.shared.distribution as distribution


def test_bundled_resource_path_uses_source_tree_when_not_frozen(monkeypatch):
    monkeypatch.delattr(distribution.sys, "_MEIPASS", raising=False)

    path = distribution.bundled_resource_path("icons", "play-line.svg")

    assert path == Path(distribution.__file__).resolve().parents[2] / "app" / "ui" / "qt" / "resources" / "icons" / "play-line.svg"


def test_bundled_resource_path_uses_pyinstaller_bundle_root(monkeypatch, tmp_path):
    monkeypatch.setattr(distribution.sys, "_MEIPASS", str(tmp_path), raising=False)

    path = distribution.bundled_resource_path("icons", "play-line.svg")

    assert path == tmp_path / "app" / "ui" / "qt" / "resources" / "icons" / "play-line.svg"


def test_configure_qt_application_metadata_sets_expected_values():
    q_app = MagicMock()

    distribution.configure_qt_application_metadata(q_app)

    q_app.setApplicationName.assert_called_once_with(distribution.APP_NAME)
    q_app.setApplicationDisplayName.assert_called_once_with(distribution.APP_NAME)
    q_app.setApplicationVersion.assert_called_once_with(distribution.APP_VERSION)
    q_app.setOrganizationName.assert_called_once_with(distribution.APP_ORGANIZATION_NAME)
