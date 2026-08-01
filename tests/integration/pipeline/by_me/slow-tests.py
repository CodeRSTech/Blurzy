# test_ui_models.py
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog

from app.application.application import Application
from app.domain import VideoDataLayer, SessionId
from app.ui.qt.main_window import MainWindow
from app.ui.state.preview_state import ToolMode
from app.ui.uicontroller import UIController


def test_change_detection_model(qtbot, qapp):
    # 1. SETUP
    app = Application()
    window = MainWindow()
    controller = UIController(q_app=qapp, window=window, app=app)
    qtbot.addWidget(window)

    test_path = "D:/minmal_people_detection.mp4"
    test_model = "YOLOv8n"
    controller.session_handler.on_open_videos([test_path])
    s_id = SessionId(test_path)

    # 2. ACT: Change the model
    dialog_path = (
        "app.ui.qt.dialogue_boxes.model_change_dlg.ModelChangeWarningDialog.exec"
    )

    with patch(dialog_path, return_value=QDialog.DialogCode.Accepted):
        window.right_panel.model_combo_box.setCurrentText(test_model)

    # 3. WAIT & ASSERT
    def check_model_loaded_successfully():
        # Verify the Domain State updated
        settings = app.get_session_settings(s_id)
        assert settings.detection_model_name == test_model, (
            "Session's detection model name does NOT match the test_model name"
        )
        # FIX: We MUST wait for the background QThread to finish!
        # We know it's finished when the UI enables the combobox again.
        assert window.right_panel.model_combo_box.isEnabled() is True

    qtbot.waitUntil(check_model_loaded_successfully, timeout=10000)

    # FIX: Graceful teardown to kill all background threads before Pytest destroys the window.
    controller.on_about_to_quit()


def test_detection_and_tracking_on_small_video(qtbot, qapp):
    # 1. SETUP
    app = Application()
    window = MainWindow()
    controller = UIController(q_app=qapp, window=window, app=app)
    qtbot.addWidget(window)

    test_path = "D:/minmal_people_detection.mp4"
    test_model = "YOLOv8n"
    model_change_dialog_path = (
        "app.ui.qt.dialogue_boxes.model_change_dlg.ModelChangeWarningDialog.exec"
    )
    num_expected_layer_a_items = 18

    controller.session_handler.on_open_videos([test_path])

    s_id = SessionId(path=test_path)
    assert s_id.path is app.active_session_id.path, (
        "Active session path and test_path are different."
    )

    # 2. ACT: Change the model
    with patch(model_change_dialog_path, return_value=QDialog.DialogCode.Accepted):
        window.right_panel.model_combo_box.setCurrentText(test_model)

    # 3. WAIT & ASSERT
    def model_loaded_successfully():
        # Verify the Domain State updated
        settings = app.get_session_settings(s_id)
        return (
            settings.detection_model_name == test_model
            and window.right_panel.model_combo_box.isEnabled() is True
        )

    while not model_loaded_successfully():
        qtbot.wait(500)

    controller.detection_handler.on_start_background_detection()

    def detection_completed():
        detection_worker = app.active_session.detection_worker
        return detection_worker is not None and detection_worker.is_complete()

    while not detection_completed():
        qtbot.wait(500)

    assert len(app.active_session.data._data["a"]) == num_expected_layer_a_items, (
        "Layer A does NOT have the correct number of items."
    )
    window.right_panel._emit_start_tracking()

    def tracking_completed():
        tracking_worker = app.active_session.tracking_worker
        return tracking_worker is not None and tracking_worker.is_complete()

    while not tracking_completed():
        qtbot.wait(500)

    print("=============================\n"
          "!!! LAYERS AFTER TRACKING !!!\n"
          "=============================")
    for layer_name in [VideoDataLayer.A, VideoDataLayer.B, VideoDataLayer.C, VideoDataLayer.D]:
        boxes = app.active_session.data.get_all_boxes_for_layer_as_dict_of_lists(layer_name)
        print("'{}' : {} items".format(layer_name, len(boxes)))


def test_user_can_draw_bounding_box(qtbot, qapp):
    # 1. SETUP
    app = Application()
    window = MainWindow()
    controller = UIController(q_app=qapp, window=window, app=app)
    qtbot.addWidget(window)

    test_path = "D:/minmal_people_detection.mp4"
    # We must intercept the LabelDialog so it doesn't freeze the test runner
    exec_patch = "app.ui.qt.dialogue_boxes.label_dlg.LabelDialog.exec"
    label_patch = "app.ui.qt.dialogue_boxes.label_dlg.LabelDialog.get_label"

    controller.session_handler.on_open_videos([test_path])
    s_id = SessionId(test_path)

    worker = app.get_session_by_id(s_id).video_decode_worker
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=2000):
        pass

    window.tool_mode_changed.emit(ToolMode.ADD)
    overlay_widget = window.preview_container.bbox_layer

    start_point = QPoint(50, 50)
    end_point = QPoint(150, 150)

    # 2. ACT: Patch the LabelDialog and simulate the mouse drag

    with (
        patch(exec_patch, return_value=QDialog.DialogCode.Accepted),
        patch(label_patch, return_value="Car"),
    ):
        # Simulate the physical drag and drop INSIDE the patch context
        qtbot.mousePress(overlay_widget, Qt.MouseButton.LeftButton, pos=start_point)
        qtbot.mouseMove(overlay_widget, pos=end_point)
        qtbot.mouseRelease(overlay_widget, Qt.MouseButton.LeftButton, pos=end_point)

    # 3. ASSERT: Did the backend register the detection?
    session = app.get_session_by_id(s_id)
    frame_index = session.state.playback.current_frame_index
    boxes_in_memory = session.get_layer_boxes_for_index(VideoDataLayer.B, frame_index)

    assert len(boxes_in_memory) == 1, "The backend failed to register the drawn detection."
    assert len(overlay_widget._active_bboxes) == 1, (
        "The UI widget didn't receive the detection to draw."
    )

    # FIX: Graceful teardown
    controller.on_about_to_quit()
