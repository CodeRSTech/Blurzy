from __future__ import annotations

import os
from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog

from app.shared.app_preferences import AppPreferencesStore
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.ui.uicontroller import UIController


logger = get_logger("UI->ProjectHandler")


@final
class ProjectHandler(QObject):
    def __init__(self, controller: UIController) -> None:
        super().__init__()
        self.setParent(controller)
        self._controller = controller
        self._window = controller.window
        self._app = controller.app
        self._preferences_store = AppPreferencesStore()
        self._connect_signals()
        self._window.set_current_project_path(self._app.current_project_path)

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        self._window.new_project_action.triggered.connect(self.on_new_project)
        self._window.open_project_action.triggered.connect(self.on_open_project)
        self._window.save_project_action.triggered.connect(self.on_save_project)
        self._window.save_project_as_action.triggered.connect(self.on_save_project_as)

    def _project_dialog_directory(self) -> str:
        if self._app.current_project_path:
            return os.path.dirname(self._app.current_project_path)
        return self._preferences_store.load().last_project_directory

    def _remember_project_directory(self, file_path: str) -> None:
        directory = os.path.dirname(file_path)
        preferences = self._preferences_store.load()
        preferences.last_project_directory = directory
        self._preferences_store.save(preferences)

    def _refresh_ui_after_project_change(self, project_path: str, status_text: str) -> None:
        self._controller.session_handler.refresh_session_views()
        self._window.set_current_project_path(project_path)
        self._window.set_status_text(status_text)

    def _show_partial_load_warning(self, skipped_missing_paths: list[str]) -> None:
        formatted_paths = "\n".join(f"- {path}" for path in skipped_missing_paths)
        self._window.show_warning(
            "Project Partially Loaded",
            "Some project video files were missing and were skipped:\n"
            f"{formatted_paths}",
        )

    @Slot()
    def on_new_project(self) -> None:
        logger.debug("Starting a new project")
        self._app.clear_project()
        self._window.bottom_panel.update_session_file_list([])
        self._controller.session_handler.update_video_related_widgets_state(False)
        self._window.set_current_project_path("")
        self._window.set_status_text("Started a new project.")

    @Slot()
    def on_open_project(self) -> None:
        start_dir = self._project_dialog_directory()
        path, _ = QFileDialog.getOpenFileName(
            self._window,
            "Open Project",
            start_dir,
            "Blurzy Project Files (*.blurzy);;JSON Files (*.json)",
        )
        if not path:
            return

        try:
            report = self._app.load_project(path)
            self._remember_project_directory(path)
            self._refresh_ui_after_project_change(path, f"Project loaded: {os.path.basename(path)}")
            if report.skipped_missing_paths:
                self._show_partial_load_warning(report.skipped_missing_paths)
        except Exception as exc:
            self._window.show_error("Open Project Failed", str(exc))
            logger.opt(exception=exc).error("Failed to open project '{}'", path)

    @Slot()
    def on_save_project(self) -> None:
        path = self._app.current_project_path
        if not path:
            self.on_save_project_as()
            return

        try:
            self._app.save_project(path)
            self._remember_project_directory(path)
            self._refresh_ui_after_project_change(path, f"Project saved: {os.path.basename(path)}")
        except Exception as exc:
            self._window.show_error("Save Project Failed", str(exc))
            logger.opt(exception=exc).error("Failed to save project '{}'", path)

    @Slot()
    def on_save_project_as(self) -> None:
        start_dir = self._project_dialog_directory()
        path, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save Project As",
            os.path.join(start_dir, "project.blurzy") if start_dir else "project.blurzy",
            "Blurzy Project Files (*.blurzy)",
        )
        if not path:
            return
        if not path.lower().endswith(".blurzy"):
            path += ".blurzy"

        try:
            self._app.save_project(path)
            self._remember_project_directory(path)
            self._refresh_ui_after_project_change(path, f"Project saved: {os.path.basename(path)}")
        except Exception as exc:
            self._window.show_error("Save Project Failed", str(exc))
            logger.opt(exception=exc).error("Failed to save project '{}'", path)
