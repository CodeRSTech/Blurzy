# app/ui/qt/model_change.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QLabel,
    QCheckBox,
    QWidget
)


class ModelChangeWarningDialog(QDialog):
    """
    Warns the user that changing model clears detections,
    and offers to retain manual annotations.
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Change Detection Model")
        self.setFixedWidth(350)

        layout = QVBoxLayout(self)

        self.warning_label = QLabel(
            "Changing the detection model will remove all existing model detections "
            "and tracking results from this session. Do you want to proceed?"
        )
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)

        self.keep_manual_cb = QCheckBox("Keep manual annotations")
        self.keep_manual_cb.setChecked(True) # Default to safe behavior
        layout.addWidget(self.keep_manual_cb)

        self.dont_ask_cb = QCheckBox("Don't ask again")
        layout.addWidget(self.dont_ask_cb)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_results(self) -> tuple[bool, bool]:
        """Returns (keep_manual, dont_ask_again)"""
        return self.keep_manual_cb.isChecked(), self.dont_ask_cb.isChecked()