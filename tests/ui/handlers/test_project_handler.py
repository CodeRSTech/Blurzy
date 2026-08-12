from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock


class _QObjectStub:
    def __init__(self, *args, **kwargs):
        pass

    def setParent(self, parent) -> None:
        self.parent = parent


_qtcore_module = sys.modules.get("PySide6.QtCore")
if _qtcore_module is not None:
    _qtcore_module.QObject = _QObjectStub

from app.shared.app_preferences import AppPreferences

_MODULE_PATH = (
    "/home/runner/work/Blurzy-development/Blurzy-development/"
    "src/app/ui/handlers/project_handler.py"
)
_spec = importlib.util.spec_from_file_location("project_handler_under_test", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
project_handler_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(project_handler_module)
ProjectHandler = project_handler_module.ProjectHandler


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class _Action:
    def __init__(self) -> None:
        self.triggered = _Signal()


@dataclass
class _BottomPanel:
    update_session_file_list: object = MagicMock()


class _Window:
    def __init__(self) -> None:
        self.new_project_action = _Action()
        self.open_project_action = _Action()
        self.save_project_action = _Action()
        self.save_project_as_action = _Action()
        self.bottom_panel = _BottomPanel()
        self.current_project_path = None
        self.status_text = None
        self.errors = []

    def set_current_project_path(self, path: str) -> None:
        self.current_project_path = path

    def set_status_text(self, text: str) -> None:
        self.status_text = text

    def show_error(self, title: str, msg: str) -> None:
        self.errors.append((title, msg))


class _PreferencesStore:
    def __init__(self) -> None:
        self.preferences = AppPreferences()

    def load(self) -> AppPreferences:
        return self.preferences

    def save(self, preferences: AppPreferences) -> None:
        self.preferences = preferences


class TestProjectHandler:
    def test_save_project_as_appends_extension_and_updates_project_display(self, monkeypatch, tmp_path) -> None:
        window = _Window()
        app = MagicMock()
        app.current_project_path = ""
        controller = MagicMock()
        controller.window = window
        controller.app = app
        controller.session_handler = MagicMock()

        monkeypatch.setattr(project_handler_module, "AppPreferencesStore", _PreferencesStore)
        monkeypatch.setattr(
            project_handler_module.QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *args, **kwargs: (str(tmp_path / "demo"), "")),
        )

        handler = ProjectHandler(controller)
        handler.on_save_project_as()

        expected_path = str(tmp_path / "demo.blurzy")
        app.save_project.assert_called_once_with(expected_path)
        assert window.current_project_path == expected_path
        assert window.status_text == "Project saved: demo.blurzy"
        controller.session_handler.refresh_session_views.assert_called_once_with()

    def test_new_project_clears_project_display(self, monkeypatch) -> None:
        window = _Window()
        app = MagicMock()
        app.current_project_path = "/tmp/existing.blurzy"
        controller = MagicMock()
        controller.window = window
        controller.app = app
        controller.session_handler = MagicMock()

        monkeypatch.setattr(project_handler_module, "AppPreferencesStore", _PreferencesStore)

        handler = ProjectHandler(controller)
        handler.on_new_project()

        app.clear_project.assert_called_once_with()
        assert window.current_project_path == ""
        assert window.status_text == "Started a new project."
