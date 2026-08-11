from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtWidgets import QDialog, QLineEdit, QLabel, QDialogButtonBox, QVBoxLayout
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget



class LabelDialog(QDialog):
    """Simple dialog to collect a label string after a bbox has been drawn interactively."""

    def __init__(self, parent: QWidget | None = None, *, initial_label: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Label")
        self.setFixedWidth(300)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. person, car, face...")
        self._label_edit.setText(initial_label)

        hint = QLabel("Draw a detection on the preview, then enter its label.")
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self._label_edit)
        layout.addWidget(buttons)

        self._label_edit.returnPressed.connect(self.accept)

    def get_label(self) -> str:
        return self._label_edit.text().strip()
