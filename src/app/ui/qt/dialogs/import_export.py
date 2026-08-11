"""Import / Export layer data dialog.

Shown when the user clicks either "Import / Export" button on the right panel.
The dialog is *scope-aware*: the detection button opens it scoped to layers A/B,
while the tracking button opens it scoped to layers C/D.

Result
------
After the user clicks OK, call :meth:`ImportExportDialog.get_config` to receive
an :class:`ImportExportConfig` dataclass.  If the dialog was rejected or the user
cancelled the overwrite-warning confirmation, ``get_config()`` returns ``None``.

⚠️  KNOWN QT QVARIANT COERCION ISSUE — READ BEFORE EDITING
============================================================
``VideoDataLayer`` and ``ImportMode`` are both ``str``-based enums:
    class VideoDataLayer(str, Enum): A = "a" …
    class ImportMode(str, Enum):     OVERWRITE = "overwrite" …

When any Python object that is a *subclass of ``str``* is stored as userData in a
``QComboBox`` via ``addItem(label, userData)`` and retrieved via ``currentData()``,
PySide6's internal Qt ``QVariant`` machinery sees a plain string (because the object
IS-A str), discards the Python subclass identity, and returns a bare ``str``.

Concretely:
    self._layer_combo.addItem("Layer A", VideoDataLayer.A)  # enum IN
    self._layer_combo.currentData()                          # "a" OUT  ← coerced!

This caused:
    cfg.layer = "a"            # plain str, not VideoDataLayer.A
    cfg.layer.name             # AttributeError: 'str' object has no attribute 'name'

Observed in the logs as:
    WARNING  | DetectionExportService was provided with string literal 'a'
    ERROR    | AttributeError: 'str' object has no attribute 'name'

Fix applied in THREE places (belt-and-suspenders):
    1. PRIMARY:   _build_config() calls ensure_layer_enum() and
                  ensure_import_mode() immediately after currentData() so coerced
                  strings are converted back to enums before leaving the dialog.
    2. SECONDARY: All import/export services coerce incoming layer/mode values
                  at their entry points as a safety net for programmatic callers.
    3. TERTIARY:  Application facade methods coerce at the boundary before
                  dispatching to detection/tracking service implementations.

No signals/slots are involved in the coercion — it is a synchronous round-trip
through Qt's QVariant heap:
    QDialogButtonBox.accepted → _on_accepted() → _build_config() → currentData()

DO NOT remove ensure_layer_enum()/ensure_import_mode() calls without understanding this.
See: app/application/services/layer_coercion.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from dataclasses import dataclass
from typing import final

from PySide6.QtWidgets import QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton

from app.application.services.helpers.layer_coercion import ensure_import_mode, ensure_layer_enum
from app.application.services.helpers.import_mode import ImportMode
from app.domain.video.layer import VideoDataLayer
from app.ui.qt.shared.layout_shortcuts import create_hbox_layout, create_vbox_layout
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget



# ──────────────────────────────────────────────────────────────────────────────
#  Result type
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ImportExportConfig:
    """
    Immutable result returned by :meth:`ImportExportDialog.get_config`.

    Attributes:
        is_import:   ``True``  → the user chose Import.
                     ``False`` → the user chose Export.
        layer:       The target/source :class:`VideoDataLayer`.
        fmt:         ``"json"`` or ``"csv"``.
        file_path:   Absolute path selected by the user.
        import_mode: The chosen :class:`ImportMode`; ``None`` for exports.
    """
    is_import: bool
    layer: VideoDataLayer
    fmt: str
    file_path: str
    import_mode: ImportMode | None


# ──────────────────────────────────────────────────────────────────────────────
#  Dialog
# ──────────────────────────────────────────────────────────────────────────────

# Human-readable labels for the layer combo box
_LAYER_LABELS: dict[VideoDataLayer, str] = {
    VideoDataLayer.A: "Layer A — Raw Detections",
    VideoDataLayer.B: "Layer B — Reviewed Detections",
    VideoDataLayer.C: "Layer C — Raw Tracks",
    VideoDataLayer.D: "Layer D — Reviewed Tracks",
}

# Note: the dialog intentionally allows cross-scope imports (e.g. exporting
# from Layer A and importing into Layer C) because the feature spec says
# "user can export from any layer and import into any layer".
# The ``scope_layers`` parameter merely determines which layers are *shown*
# in this particular dialog instance (detection context → A/B, tracking → C/D).


@final
class ImportExportDialog(QDialog):
    """
    Modal dialog for importing or exporting bounding-box layer data.

    Args:
        scope_layers: Layers to offer in the layer combo box.
        scope_title:  Human-readable scope label shown in the window title.
        parent:       Optional Qt parent widget.

    Usage::

        dlg = ImportExportDialog(
            scope_layers=[VideoDataLayer.A, VideoDataLayer.B],
            scope_title="Detection",
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg = dlg.get_config()
            if cfg:   # None if the user cancelled the overwrite warning
                ...

    Note:
        The dialog enforces the overwrite warning itself (before calling
        ``accept()``) so the handler does not need to show a second dialog.

        Consider future improvement: persist the last-used directory per scope
        (detection / tracking) using ``QSettings`` so the file browser opens
        in a sensible location across sessions.
    """

    def __init__(
        self,
        scope_layers: list[VideoDataLayer],
        scope_title: str = "Layer",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Import / Export — {scope_title} Data")
        self.setMinimumWidth(520)

        self._scope_layers = scope_layers
        self._config: ImportExportConfig | None = None

        self._init_widgets()
        self._build_ui()
        self._connect_signals()
        self._refresh_ui_state()

    # ──────────────────────────────────────────────────────────────────────
    #  Widget initialisation
    # ──────────────────────────────────────────────────────────────────────

    def _init_widgets(self) -> None:
        # -- Operation selector -----------------------------------------------
        self._radio_import = QRadioButton("Import into layer")
        self._radio_export = QRadioButton("Export from layer")
        self._radio_import.setChecked(True)

        self._operation_group = QButtonGroup(self)
        self._operation_group.addButton(self._radio_import)
        self._operation_group.addButton(self._radio_export)

        # -- Layer combo -------------------------------------------------------
        self._layer_combo = QComboBox()
        for layer in self._scope_layers:
            # [QVariant COERCION RISK] VideoDataLayer is a str-based enum.
            # addItem() stores userData via Qt's QVariant heap. On retrieval via
            # currentData(), Qt sees a str subclass, strips the Python subclass
            # identity, and returns a bare str ("a", "b", etc.) instead of the
            # enum member. ensure_layer_enum() in _build_config() re-wraps it.
            self._layer_combo.addItem(_LAYER_LABELS.get(layer, layer.name), layer)

        # -- Format combo ------------------------------------------------------
        self._format_combo = QComboBox()
        self._format_combo.addItem("JSON  (.json)", "json")
        self._format_combo.addItem("CSV   (.csv)", "csv")

        # -- Import mode combo (import only) -----------------------------------
        self._mode_combo = QComboBox()
        for mode in ImportMode:
            # [QVariant COERCION RISK] ImportMode is also a str-based enum and
            # suffers the same QVariant round-trip coercion as VideoDataLayer
            # above. If mode.display_label is accessed on the raw currentData()
            # result, it will raise AttributeError. ensure_layer_enum() does not
            # handle ImportMode — add a dedicated coercion if needed in future.
            self._mode_combo.addItem(mode.display_label, mode)
        self._mode_label = QLabel("Merge strategy:")

        # -- File path ---------------------------------------------------------
        self._file_edit = QLineEdit()
        self._file_edit.setReadOnly(True)
        self._file_edit.setPlaceholderText("Select a file…")
        self._browse_btn = QPushButton("Browse…")

        # -- Warning label (import) --------------------------------------------
        self._overwrite_hint = QLabel(
            "⚠️  Importing will modify the selected layer.  "
            "You will be asked to confirm before data is changed."
        )
        self._overwrite_hint.setWordWrap(True)
        self._overwrite_hint.setStyleSheet("color: #d9534f;")

        # -- Dialog buttons ----------------------------------------------------
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel  # type: ignore[operator]
        )
        self._button_box.accepted.connect(self._on_accepted)
        self._button_box.rejected.connect(self.reject)

    def _build_ui(self) -> None:
        root = create_vbox_layout(self, spacing=12)

        # Operation group box
        op_box = QGroupBox("Operation")
        create_hbox_layout(op_box, widgets=(self._radio_import, self._radio_export))
        root.addWidget(op_box)

        # Options form
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Layer:", self._layer_combo)
        form.addRow("Format:", self._format_combo)
        form.addRow(self._mode_label, self._mode_combo)
        root.addLayout(form)

        # File selector row
        file_row = create_hbox_layout(widgets=(self._file_edit, self._browse_btn))
        root.addLayout(file_row)

        # Warning
        root.addWidget(self._overwrite_hint)

        root.addStretch()
        root.addWidget(self._button_box)

    # ──────────────────────────────────────────────────────────────────────
    #  Signal wiring
    # ──────────────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._radio_import.toggled.connect(self._refresh_ui_state)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._browse_btn.clicked.connect(self._on_browse)

    # ──────────────────────────────────────────────────────────────────────
    #  UI view_state helpers
    # ──────────────────────────────────────────────────────────────────────

    def _refresh_ui_state(self) -> None:
        """Show/hide import-only widgets based on current operation radio."""
        is_import = self._radio_import.isChecked()
        self._mode_label.setVisible(is_import)
        self._mode_combo.setVisible(is_import)
        self._overwrite_hint.setVisible(is_import)
        self._update_ok_button()

    def _on_format_changed(self) -> None:
        """Clear the file path when the format changes to avoid extension mismatches."""
        self._file_edit.clear()
        self._update_ok_button()

    def _update_ok_button(self) -> None:
        ok = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setEnabled(bool(self._file_edit.text().strip()))

    # ──────────────────────────────────────────────────────────────────────
    #  Browse button
    # ──────────────────────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        fmt: str = self._format_combo.currentData()
        ext_label = "JSON Files (*.json)" if fmt == "json" else "CSV Files (*.csv)"
        ext = f".{fmt}"

        if self._radio_import.isChecked():
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Import File", "", ext_label
            )
        else:
            default_name = f"layer_export{ext}"
            path, _ = QFileDialog.getSaveFileName(
                self, "Select Export Destination", default_name, ext_label
            )

        if path:
            # Ensure the extension matches the chosen format
            if not path.lower().endswith(ext):
                path += ext
            self._file_edit.setText(path)
            self._update_ok_button()

    # ──────────────────────────────────────────────────────────────────────
    #  Accept / confirm
    # ──────────────────────────────────────────────────────────────────────

    def _on_accepted(self) -> None:
        """Validate, optionally show the overwrite confirmation, then accept."""
        file_path = self._file_edit.text().strip()
        if not file_path:
            return

        if self._radio_import.isChecked():
            # -- Overwrite warning before any data is touched -----------------
            mode: ImportMode = ensure_import_mode(self._mode_combo.currentData())
            # [QVariant COERCION NOTE] layer/mode may arrive here as bare str values
            # due to the QVariant round-trip. _LAYER_LABELS.get() uses enum keys,
            # so the lookup will miss and fall back to layer.name — which fails if
            # layer is a str. mode.display_label also fails if mode is a str.
            # ensure_layer_enum()/ensure_import_mode() in _build_config() are the
            # authoritative fixes; this call is inside the import-only branch and
            # executes before _build_config, so we coerce defensively here too.
            layer: VideoDataLayer = ensure_layer_enum(self._layer_combo.currentData())
            layer_label = _LAYER_LABELS.get(layer, layer.name)
            mode_label = mode.display_label

            msg = (
                f"You are about to import data into <b>{layer_label}</b>.<br><br>"
                f"Merge strategy: <b>{mode_label}</b><br><br>"
                "This operation <b>cannot be undone</b>.  Continue?"
            )
            reply = QMessageBox.warning(
                self,
                "Confirm Import",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                # User backed out — do not accept, leave dialog open
                return

        self._build_config(file_path)
        self.accept()

    def _build_config(self, file_path: str) -> None:
        # [PRIMARY FIX — QVariant coercion] currentData() returns a bare str
        # for str-based enums (see module docstring for the full explanation).
        # ensure_layer_enum() converts "a" / "b" / "c" / "d" back to the correct
        # VideoDataLayer enum member so that cfg.layer is always a proper enum
        # by the time it leaves the dialog.  The downstream services also call
        # ensure_layer_enum() as a secondary safety net.
        self._config = ImportExportConfig(
            is_import=self._radio_import.isChecked(),
            layer=ensure_layer_enum(self._layer_combo.currentData()),
            fmt=self._format_combo.currentData(),
            file_path=file_path,
            import_mode=(
                ensure_import_mode(self._mode_combo.currentData())
                if self._radio_import.isChecked()
                else None
            ),
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────────────────────────────

    def get_config(self) -> ImportExportConfig | None:
        """
        Return the user's choices after the dialog was accepted.

        Returns:
            :class:`ImportExportConfig` if the user confirmed, otherwise ``None``.
        """
        return self._config
