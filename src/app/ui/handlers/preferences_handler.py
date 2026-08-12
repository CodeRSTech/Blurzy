from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QDialog

from app.infrastructure.detection.model.helpers import get_available_detection_model_names_as_view_model
from app.shared.app_preferences import AppPreferences, AppPreferencesStore
from app.shared.logging_cfg import get_logger
from app.ui.qt.dialogs import PreferencesDialog

if TYPE_CHECKING:
    from app.domain.session import SessionId
    from app.ui.uicontroller import UIController


logger = get_logger("UI->PreferencesHandler")


@final
class PreferencesHandler(QObject):
    """Manage persistent app preferences and session-default application."""

    def __init__(self, controller: UIController) -> None:
        super().__init__()
        self.setParent(controller)
        self._controller = controller
        self._window = controller.window
        self._app = controller.app
        self._store = AppPreferencesStore()
        self._preferences = self._store.load()
        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    @property
    def preferences(self) -> AppPreferences:
        return self._preferences

    def _connect_signals(self) -> None:
        self._window.preferences_action.triggered.connect(self.on_preferences_requested)

    def _apply_window_preferences(self) -> None:
        if self._preferences.startup_fullscreen:
            if not self._window.isFullScreen():
                self._window.showFullScreen()
            return
        if self._window.isFullScreen():
            self._window.showNormal()

    def apply_defaults_to_session(self, s_id: SessionId) -> None:
        logger.debug("Applying saved default session settings to {}", s_id)
        self._app.update_session_settings(s_id, **self._preferences.to_processing_settings_kwargs())

    @Slot()
    def on_preferences_requested(self) -> None:
        dialog = PreferencesDialog(
            preferences=self._preferences,
            available_models=get_available_detection_model_names_as_view_model(),
            parent=self._window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._preferences = dialog.get_preferences()
        self._store.save(self._preferences)
        self._apply_window_preferences()
        self._window.set_status_text(
            "Settings saved. New session defaults will apply to videos opened from now on."
        )
