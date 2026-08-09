"""Import / Export handler for detection and tracking layer data."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QObject, Slot

from app.application.services.helpers.layer_coercion import ensure_layer_enum
from app.domain.video.layer import VideoDataLayer
from app.shared.exceptions import UnsupportedImportExportFormatException, UnsupportedLayerOperationException
from app.shared.logging_cfg import get_logger
from app.ui.qt.dialogs.import_export import ImportExportDialog

if TYPE_CHECKING:
    from app.ui.uicontroller import UIController

logger = get_logger("UI->ImportExportHandler")


@final
class ImportExportHandler(QObject):
    """
    Handles import and export operations for detection layers (A/B) and
    tracking layers (C/D).

    Responsibilities:
        - Open :class:`~app.ui.qt.dialogs.import_export_dlg.ImportExportDialog`
          scoped to the appropriate layers when either "Import / Export" button is clicked.
        - Dispatch the user's choice to
          :meth:`Application.import_layer` or :meth:`Application.export_layer`.
        - Trigger a frame re-render after a successful import so the UI reflects
          the newly loaded data immediately.
        - Show a success / error status message via the window's status bar.

    Note:
        Signal flow::

            right_panel.imp_exp_detections_button.clicked
              └──> on_import_export_detections()
                    └──> _run_import_export(scope=[A, B], title="Detection")

            right_panel.imp_exp_tracks_button.clicked
              └──> on_import_export_tracks()
                    └──> _run_import_export(scope=[C, D], title="Tracking")

        After a successful *import* the handler calls
        ``controller.render_frame_for_session_id()`` so the video preview
        updates without the user having to scrub the timeline.

        After a successful *export* only a status-bar message is shown — no
        re-render is needed because the session data was not modified.

        Consider future improvement: run the actual file I/O in a background
        QThread (similar to how DetectionWorker / TrackingWorker operate) so
        that very large files do not freeze the UI during deserialisation.
    """

    def __init__(self, controller: UIController) -> None:
        super().__init__(parent=controller)
        self._controller = controller
        self._window = controller.window
        self._app = controller.app

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        right_panel = self._window.right_panel
        right_panel.imp_exp_detections_button.clicked.connect(
            self.on_import_export_detections
        )
        right_panel.imp_exp_tracks_button.clicked.connect(
            self.on_import_export_tracks
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Public slots
    # ──────────────────────────────────────────────────────────────────────

    @Slot()
    def on_import_export_detections(self) -> None:
        """
        Open the Import / Export dialog scoped to detection layers A and B.

        **Triggered By:**
            Right panel ``imp_exp_detections_button.clicked``
        """
        self._run_import_export(
            scope=[VideoDataLayer.A, VideoDataLayer.B],
            scope_title="Detection",
        )

    @Slot()
    def on_import_export_tracks(self) -> None:
        """
        Open the Import / Export dialog scoped to tracking layers C and D.

        **Triggered By:**
            Right panel ``imp_exp_tracks_button.clicked``
        """
        self._run_import_export(
            scope=[VideoDataLayer.C, VideoDataLayer.D],
            scope_title="Tracking",
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Core dispatch
    # ──────────────────────────────────────────────────────────────────────

    def _run_import_export(
        self,
        scope: list[VideoDataLayer],
        scope_title: str,
    ) -> None:
        """Open the dialog, then dispatch import or export to the Application."""
        # ====================================================================
        # 1. VALIDATE SESSION
        # ====================================================================
        s_id = self._window.selected_s_id
        if not s_id:
            self._window.show_error(
                "No Session Selected",
                "Please open a video session before importing or exporting.",
            )
            return

        # ====================================================================
        # 2. SHOW DIALOG
        # ====================================================================
        dlg = ImportExportDialog(
            scope_layers=scope,
            scope_title=scope_title,
            parent=self._window,
        )
        if dlg.exec() != ImportExportDialog.DialogCode.Accepted:
            return

        cfg = dlg.get_config()
        if cfg is None:
            # User cancelled the overwrite confirmation inside the dialog
            return

        # ====================================================================
        # 3. DISPATCH
        # ====================================================================
        try:
            if cfg.is_import:
                self._do_import(s_id, cfg)
            else:
                self._do_export(s_id, cfg)
        except UnsupportedImportExportFormatException as exc:
            self._window.show_error("Import / Export Failed", str(exc))
            logger.warning("Import/Export operation failed with unsupported format: {}", exc)
        except UnsupportedLayerOperationException as exc:
            self._window.show_error("Import / Export Failed", str(exc))
            logger.warning("Import/Export operation failed with unsupported layer: {}", exc)
        except Exception as exc:
            self._window.show_error("Import / Export Failed", str(exc))
            logger.opt(exception=exc).error(
                "Import/Export operation failed for session '{}'", s_id
            )

    def _do_import(self, s_id, cfg) -> None:
        # ====================================================================
        # 3a. IMPORT — write data into the target layer
        # ====================================================================
        # [NOTE] Coerce cfg.layer to enum in case Qt signal/slot coerced it to string
        layer = ensure_layer_enum(cfg.layer)
        if cfg.import_mode is None:
            # Defensive guard: import flow must always carry an import mode.
            # If this ever triggers, the dialog config contract has regressed.
            raise ValueError("Import mode is required for import operations.")

        total = self._app.import_layer(
            s_id=s_id,
            layer=layer,
            file_path=cfg.file_path,
            mode=cfg.import_mode,
        )

        logger.info(
            "Import complete: {} box(es) into layer '{}' for session '{}'",
            total, layer, s_id,
        )

        # Re-render current frame so changes are immediately visible
        self._controller.render_frame_for_session_id(s_id)
        self._window.set_status_text(
            f"Import complete — {total} box(es) loaded into layer {layer.name}."
        )

    def _do_export(self, s_id, cfg) -> None:
        # ====================================================================
        # 3b. EXPORT — read data from the source layer and write to file
        # ====================================================================
        # [NOTE] Coerce cfg.layer to enum in case Qt signal/slot coerced it to string
        layer = ensure_layer_enum(cfg.layer)

        total = self._app.export_layer(
            s_id=s_id,
            layer=layer,
            file_path=cfg.file_path,
        )

        logger.info(
            "Export complete: {} box(es) from layer '{}' for session '{}' → '{}'",
            total, layer, s_id, cfg.file_path,
        )

        self._window.set_status_text(
            f"Export complete — {total} box(es) from layer {layer.name} "
            f"saved to '{cfg.file_path}'."
        )
