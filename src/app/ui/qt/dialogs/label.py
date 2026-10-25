"""
Module for label; implements the Qt presentation components.

See Also:
    - [`BBoxViewModel`][app.domain.views.bounding_box_view_model.BBoxViewModel] — carries the label displayed for a box
    - [`AnnotationHandler`][app.ui.handlers.annotation_handler.AnnotationHandler] — coordinates label edits

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtWidgets import QDialog, QLineEdit, QLabel, QDialogButtonBox, QVBoxLayout
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class LabelDialog(QDialog):
    """
    Simple dialog to collect a label string after a bbox has been drawn interactively.


    Args:
        parent: Optional Qt parent object.
        initial_label: Label initially shown in the editor.
    """

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
        """
        Return the entered label with surrounding whitespace removed.

        Returns:
            Stripped label text.
        """
        return self._label_edit.text().strip()
