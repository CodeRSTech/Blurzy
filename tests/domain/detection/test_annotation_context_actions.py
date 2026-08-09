# test_ui_models.py


# def test_detection_and_tracking_on_small_video(qtbot, qapp):
#     # 1. SETUP
#     app = App()
#     window = MainWindow()
#     controller = UIController(q_app=qapp, window=window, app=app)
#     qtbot.addWidget(window)
#
#     test_path = "D:/minmal_people_detection.mp4"
#     test_model = "YOLOv8n"
#     model_change_dialog_path = (
#         "app.ui.qt.dialogs.model_change_dlg.ModelChangeWarningDialog.exec"
#     )
#
#     controller.session_handler.on_open_videos([test_path])
#
#     s_id = SessionId(path=test_path)
#     assert s_id.path is app.active_session_id.path, (
#         "Active session path and test_path are different."
#     )
#
#     # 2. ACT: Change the model
#     with patch(model_change_dialog_path, return_value=QDialog.DialogCode.Accepted):
#         window.right_panel.model_combo_box.setCurrentText(test_model)
#
#     # 3. WAIT & ASSERT
#     def model_loaded_successfully():
#         # Verify the Domain State updated
#         settings = app.get_session_settings(s_id)
#         return (
#             settings.detection_model_name == test_model
#             and window.right_panel.model_combo_box.isEnabled() is True
#         )
#
#     while not model_loaded_successfully():
#         qtbot.wait(500)
#
#     controller.detection_handler.on_detect_current_frame()
#
#     window.show()
#     while True:
#         qtbot.wait(500)