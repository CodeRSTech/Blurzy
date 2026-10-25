"""Tracking preflight must not discard existing results without confirmation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from app.domain import VideoDataLayer
from app.ui.handlers.tracking_handler import TrackingHandler
from app.ui.qt.window.window import Window


@pytest.mark.parametrize(
    "processed,total,proceed,detecting,starts",
    [(1, 100, False, False, False), (1, 100, True, False, True),
     (100, 100, False, False, True), (0, 100, False, False, False),
     (100, 100, True, True, False)],
)
def test_tracking_preflight_confirmation_precedes_loading_and_worker_start(
    processed, total, proceed, detecting, starts
):
    handler = TrackingHandler.__new__(TrackingHandler)
    QObject.__init__(handler)
    handler._window = MagicMock(selected_s_id="video")
    handler._window.confirm_incomplete_detections.return_value = proceed
    handler._app = MagicMock(active_session_id="video")
    handler._app.session_has_running_tracking_worker.return_value = False
    handler._app.get_detection_frame_coverage.return_value = (processed, total)
    handler._app.get_session_by_id.return_value = SimpleNamespace(has_running_detection_worker=detecting)

    handler.on_start_tracking("hungarian", VideoDataLayer.B)

    assert handler._app.start_tracking_worker.called is starts
    assert handler._window.set_tracking_loading_state.called is starts
    if starts:
        handler._app.start_tracking_worker.assert_called_once_with("video", "hungarian", VideoDataLayer.B)
    if processed < total and not detecting:
        handler._window.confirm_incomplete_detections.assert_called_once_with(processed, total)
    else:
        handler._window.confirm_incomplete_detections.assert_not_called()
    if detecting:
        handler._window.show_error.assert_called_once()


@pytest.mark.parametrize("choice,proceeds", [("Okay", False), ("Proceed Anyway", True)])
def test_incomplete_detection_dialog_requires_explicit_proceed(qtbot, choice, proceeds):
    window = QWidget()
    qtbot.addWidget(window)
    observed_defaults = []

    def choose():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        observed_defaults.append(dialog.defaultButton().text())
        next(button for button in dialog.buttons() if button.text() == choice).click()

    QTimer.singleShot(0, choose)
    assert Window.confirm_incomplete_detections(window, 1, 100) is proceeds
    assert observed_defaults == ["Okay"]
