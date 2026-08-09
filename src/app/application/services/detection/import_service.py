"""Detection layer import service — loads bounding-box data into layers A or B."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QObject

from app.application.adapters import ApplicationAdapter
from app.application.services.helpers.layer_coercion import ensure_import_mode, ensure_layer_enum
from app.application.services.helpers.layer_io import (
    apply_import_to_layer,
    deserialize_layer_from_csv,
    deserialize_layer_from_json,
)
from app.application.services.helpers.import_mode import ImportMode
from app.domain.video.layer import VideoDataLayer
from app.shared.exceptions import UnsupportedImportExportFormatException, UnsupportedLayerOperationException
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.application import Application
    from app.domain.session.session_id import SessionId

logger = get_logger("Application->DetectionImportService")

# ---------------------------------------------------------------------------
# Layer guard — callers should only ask this service to write A or B.
# Writing to C/D here would silently corrupt tracking data.
# Note: this is a soft guard (warning only); the dialog already enforces it.
# ---------------------------------------------------------------------------
_ALLOWED_LAYERS = frozenset({VideoDataLayer.A, VideoDataLayer.B})


@final
class DetectionImportService(QObject):
    """
    Loads persisted bounding-box data into detection layers A or B.

    Responsibilities:
        - Read a JSON or CSV file produced by :class:`DetectionExportService`.
        - Apply the chosen :class:`ImportMode` merge strategy via
          :func:`~app.application.services._layer_io.apply_import_to_layer`.
        - Return the total number of boxes written for status reporting.

    Note:
        This service satisfies the :class:`~app.application.interfaces.IDataImporter`
        Protocol via structural subtyping — no explicit inheritance is needed.

        Layers A/B are the *detection* layers.  Do not use this service to write
        to tracking layers C/D; use :class:`TrackingImportService` instead.

        The ``file_path`` extension determines the format:
            ``.json`` → JSON deserialiser
            ``.csv``  → CSV  deserialiser
            Anything else raises ``ValueError``.

        Consider future improvement: add progress callbacks for very large files
        (millions of boxes across thousands of frames), similar to how the
        detection/export workers report progress today.
    """

    def __init__(self, app: Application) -> None:
        super().__init__(parent=app)
        self._app_adapter = ApplicationAdapter(app)

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def import_layer(
        self,
        s_id: SessionId,
        layer: VideoDataLayer | str,
        file_path: str,
        mode: ImportMode | str,
    ) -> int:
        """
        Import bounding-box data from ``file_path`` into ``layer``.

        Args:
            s_id:      Target session.
            layer:     Target layer — should be ``A`` or ``B`` (or their string equivalents).
            file_path: Absolute path to a ``.json`` or ``.csv`` file.
            mode:      Merge strategy (enum or string).

        Returns:
            int: Number of boxes written.

        Raises:
            ValueError: If ``file_path`` has an unrecognised extension.
            FileNotFoundError: If ``file_path`` does not exist.

        Note:
            Accepts both ``VideoDataLayer`` enums and string layer names to handle
            Qt signal/slot type coercion.
        """
        # ====================================================================
        # 0. COERCE INPUTS TO ENUMS
        # ====================================================================
        layer = ensure_layer_enum(layer)
        mode = ensure_import_mode(mode)

        if layer not in _ALLOWED_LAYERS:
            raise UnsupportedLayerOperationException("detection_import", layer)

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Import file not found: {file_path}")

        # ====================================================================
        # 1. DESERIALISE FILE
        # ====================================================================
        incoming = _load_file(file_path)

        # ====================================================================
        # 2. APPLY MERGE STRATEGY
        # ====================================================================
        session = self._app_adapter.get_session_by_id(s_id)
        total = apply_import_to_layer(session.data, layer, incoming, mode)

        logger.info(
            "DetectionImportService: imported {} box(es) into layer '{}' "
            "for session '{}' (mode={}, file='{}')",
            total, layer, s_id, mode.value, file_path,
        )
        return total


# ──────────────────────────────────────────────────────────────────────────────
#  Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_file(file_path: str) -> dict:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".json":
        return deserialize_layer_from_json(file_path)
    if ext == ".csv":
        return deserialize_layer_from_csv(file_path)
    raise UnsupportedImportExportFormatException(extension=ext, operation="detection import")
