"""
Package for dialogs; implements the Qt presentation components.

See Also:
    - [`DialogueHandler`][app.ui.handlers.dialogue_handler.DialogueHandler] — coordinates modal dialog interactions
    - [`ImportExportDialog`][app.ui.qt.dialogs.import_export.ImportExportDialog] — configures layer data import and export

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from .annotation import EditAnnotationDialog
from .export_all import ExportAllDialog
from .import_export import ImportExportDialog, ImportExportConfig
from .label import LabelDialog
from .model_change import ModelChangeWarningDialog
from .preferences import PreferencesDialog

__all__ = [
    "EditAnnotationDialog",
    "ExportAllDialog",
    "ImportExportDialog",
    "ImportExportConfig",
    "LabelDialog",
    "ModelChangeWarningDialog",
    "PreferencesDialog",
]
