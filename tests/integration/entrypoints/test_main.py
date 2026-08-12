from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

import main as main_module


class TestMainStartup:
    def test_invalid_startup_config_exits_before_bootstrapping_ui(self, monkeypatch, capsys):
        monkeypatch.setenv("BLURZY_LOG_CONSOLE_LEVEL", "verbose")
        configure_logging = MagicMock()
        configure_qt_application_metadata = MagicMock()
        monkeypatch.setattr(main_module, "configure_logging", configure_logging)
        monkeypatch.setattr(main_module, "configure_qt_application_metadata", configure_qt_application_metadata)

        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

        assert exc_info.value.code == 2
        assert "BLURZY_LOG_CONSOLE_LEVEL" in capsys.readouterr().err
        configure_logging.assert_not_called()

    def test_main_bootstraps_app_when_startup_config_is_valid(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLURZY_LOG_FILE_PATH", str(tmp_path / "app.log"))
        configure_logging = MagicMock()
        configure_qt_application_metadata = MagicMock()
        monkeypatch.setattr(main_module, "configure_logging", configure_logging)
        monkeypatch.setattr(main_module, "configure_qt_application_metadata", configure_qt_application_metadata)

        q_app_instance = MagicMock()
        q_app_instance.exec.return_value = 0
        q_application = MagicMock(return_value=q_app_instance)
        app_instance = MagicMock()
        app_cls = MagicMock(return_value=app_instance)
        window_instance = MagicMock()
        window_cls = MagicMock(return_value=window_instance)
        ui_controller_cls = MagicMock()
        apply_custom_qt_reprs = MagicMock()
        apply_qt_ui_shortcuts = MagicMock()

        def _package(name: str) -> types.ModuleType:
            module = types.ModuleType(name)
            module.__path__ = []
            return module

        qtwidgets_module = types.ModuleType("PySide6.QtWidgets")
        qtwidgets_module.QApplication = q_application
        application_module = types.ModuleType("app.application.application")
        application_module.Application = app_cls
        window_module = types.ModuleType("app.ui.qt.window")
        window_module.Window = window_cls
        qt_debug_module = types.ModuleType("app.ui.qt.shared.qt_debug_repr")
        qt_debug_module.apply_custom_qt_reprs = apply_custom_qt_reprs
        qt_ui_shortcuts_module = types.ModuleType("app.ui.qt.shared.qt_ui_shortcuts")
        qt_ui_shortcuts_module.apply_qt_ui_shortcuts = apply_qt_ui_shortcuts
        ui_controller_module = types.ModuleType("app.ui.uicontroller")
        ui_controller_module.UIController = ui_controller_cls

        monkeypatch.setitem(sys.modules, "PySide6", _package("PySide6"))
        monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets_module)
        monkeypatch.setitem(sys.modules, "app.application", _package("app.application"))
        monkeypatch.setitem(sys.modules, "app.application.application", application_module)
        monkeypatch.setitem(sys.modules, "app.ui", _package("app.ui"))
        monkeypatch.setitem(sys.modules, "app.ui.qt", _package("app.ui.qt"))
        monkeypatch.setitem(sys.modules, "app.ui.qt.shared", _package("app.ui.qt.shared"))
        monkeypatch.setitem(sys.modules, "app.ui.qt.window", window_module)
        monkeypatch.setitem(sys.modules, "app.ui.qt.shared.qt_debug_repr", qt_debug_module)
        monkeypatch.setitem(sys.modules, "app.ui.qt.shared.qt_ui_shortcuts", qt_ui_shortcuts_module)
        monkeypatch.setitem(sys.modules, "app.ui.uicontroller", ui_controller_module)

        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

        assert exc_info.value.code == 0
        configure_logging.assert_called_once_with(
            console_level="DEBUG",
            file_level="TRACE",
            log_file_path=str(tmp_path / "app.log"),
            enabled_areas=None,
        )
        apply_custom_qt_reprs.assert_called_once_with()
        apply_qt_ui_shortcuts.assert_called_once_with()
        q_application.assert_called_once_with(sys.argv)
        configure_qt_application_metadata.assert_called_once_with(q_app_instance)
        app_cls.assert_called_once_with()
        window_cls.assert_called_once_with()
        ui_controller_cls.assert_called_once_with(
            q_app_instance, window_instance, app_instance
        )
        window_instance.show.assert_called_once_with()
