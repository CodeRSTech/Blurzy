from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ExportAllDialog(QDialog):
    """
    Dialog to collect configuration for the batch export operation.
    Requires an output directory and allows optional prefix/suffix.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export All Sessions")
        self.resize(450, 150)

        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setPlaceholderText("Select a folder...")

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._on_browse)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("e.g., final_")

        self.suffix_edit = QLineEdit("_exported")
        self.suffix_edit.setPlaceholderText("e.g., _exported")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self._build_ui()
        self._update_ok_button()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Output Directory:"))
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(self.browse_button)
        layout.addLayout(dir_layout)

        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("Filename Prefix:"))
        prefix_layout.addWidget(self.prefix_edit)
        layout.addLayout(prefix_layout)

        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("Filename Suffix:"))
        suffix_layout.addWidget(self.suffix_edit)
        layout.addLayout(suffix_layout)

        layout.addStretch()
        layout.addWidget(self.button_box)

    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.dir_edit.setText(directory)
            self._update_ok_button()

    def _update_ok_button(self) -> None:
        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setEnabled(bool(self.dir_edit.text()))

    def get_export_config(self) -> tuple[str, str, str]:
        """Returns: (output_directory, prefix, suffix)"""
        return (
            self.dir_edit.text().strip(),
            self.prefix_edit.text().strip(),
            self.suffix_edit.text().strip(),
        )