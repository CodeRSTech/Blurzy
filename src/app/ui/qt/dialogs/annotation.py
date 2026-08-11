from __future__ import annotations

from typing import TYPE_CHECKING


from typing import final

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox, QVBoxLayout
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
    from app.domain.base.dtypes import BBoxXYXYTuple





@final
class EditAnnotationDialog(QDialog):
    """Full edit dialog shown when modifying an existing detection (label + bbox coords)."""

    def __init__(
            self,
            parent: QWidget | None = None,
            *,
            initial_label: str = "",
            initial_bbox_xyxy: BBoxXYXYTuple = (0, 0, 0, 0),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Annotation")

        self._label_edit = QLineEdit()
        self._label_edit.setText(initial_label)

        self._x1_spin = QSpinBox()
        self._y1_spin = QSpinBox()
        self._x2_spin = QSpinBox()
        self._y2_spin = QSpinBox()

        for spin in (self._x1_spin, self._y1_spin, self._x2_spin, self._y2_spin):
            spin.setRange(0, 100_000)

        self._x1_spin.setValue(initial_bbox_xyxy[0])
        self._y1_spin.setValue(initial_bbox_xyxy[1])
        self._x2_spin.setValue(initial_bbox_xyxy[2])
        self._y2_spin.setValue(initial_bbox_xyxy[3])

        form = QFormLayout()
        form.addRow("Label", self._label_edit)
        form.addRow("X1", self._x1_spin)
        form.addRow("Y1", self._y1_spin)
        form.addRow("X2", self._x2_spin)
        form.addRow("Y2", self._y2_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _ = buttons.accepted.connect(self.accept)
        _ = buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_annotation_data(self) -> tuple[str, BBoxXYXYTuple]:
        return (
            self._label_edit.text().strip(),
            (
                self._x1_spin.value(),
                self._y1_spin.value(),
                self._x2_spin.value(),
                self._y2_spin.value(),
            ),
        )