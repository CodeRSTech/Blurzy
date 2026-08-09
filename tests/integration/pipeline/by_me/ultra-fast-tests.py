from unittest.mock import patch
from PySide6.QtCore import Qt

from app.application.application import Application

from app.domain.session.session_id import SessionId

from app.ui.qt.window import Window
from app.ui.uicontroller import UIController


# pytest-qt provides the 'qtbot' fixture to handle background threads safely
def test_video_loads_and_buffers_seamlessly(qtbot):
    app = Application()
    # 1. Arrange: Instantiate the manager WITHOUT the UI
    test_video_path = "D://people-detection.mp4"

    # 2. Act: Open the video
    app.open_videos([test_video_path])

    s_id = SessionId(test_video_path)

    # Set it active to wake up the sleeper worker!
    app.active_session_id = s_id

    session = app.sm.get_session_by_id(s_id)
    worker = session.video_decode_worker

    # 3. Wait for the QThread to emit its seek_completed signal
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=1000):
        pass  # qtbot blocks here for a few milliseconds until the signal fires

    # 4. Assert: Verify the Ring Buffer caught the frame instantly
    frame = session.get_buffered_frame()

    assert frame is not None
    assert frame.shape == (432, 768, 3)  # Verify dimensions

def test_open_video_and_play(qtbot, qapp):
    # 1. SETUP: Initialize the Core, Window, and Controller
    app_core = Application()
    window = Window()
    UIController(q_app=qapp, window=window, app=app_core)

    # Register the window with qtbot so it cleans up after the test
    qtbot.addWidget(window)

    test_path = "D://people-detection.mp4"
    s_id = SessionId(test_path)

    # 2. ACT: Mock the File Dialog and trigger the Open Action
    # This intercepts Qt's file explorer and forces it to return our test_path instantly.
    with patch("PySide6.QtWidgets.QFileDialog.getOpenFileNames", return_value=([test_path], "")):
        # Trigger the action exactly as if the user clicked "File -> Open Videos"
        window.open_videos_action.trigger()

    session = app_core.get_session_by_id(s_id)
    worker = session.video_decode_worker

    # 3. WAIT: Wait for the background worker to safely cache Frame 0
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=2000):
        pass  # The test pauses here until the worker broadcasts its signal

    # 4. ASSERT: First frame shows without problems
    assert app_core.sm.get_current_frame_for_session_id(s_id) is not None
    assert window.selected_s_id == s_id

    # 5. ACT: Hit Play
    # Simulate a physical left-click on the play button
    qtbot.mouseClick(window.transport_panel.play_btn, Qt.MouseButton.LeftButton)

    # 6. ASSERT: Video is playing
    assert app_core.is_session_playing(s_id) is True
    # Optional: Verify the UI button updated its text/icon
    # assert window.transport_panel.play_btn.text() == "Pause"
