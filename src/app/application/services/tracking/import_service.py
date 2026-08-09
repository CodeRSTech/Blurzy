"""Tracking layer import service — loads bounding-box data into layers C or D."""

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

logger = get_logger("Application->TrackingImportService")

_ALLOWED_LAYERS = frozenset({VideoDataLayer.C, VideoDataLayer.D})


@final
class TrackingImportService(QObject):
    """
    Loads persisted bounding-box data into tracking layers C or D.

    Responsibilities:
        - Read a JSON or CSV file produced by :class:`TrackingExportService`
          (or any exporter that uses the shared wire format).
        - Apply the chosen :class:`ImportMode` merge strategy.
        - Return the total number of boxes written.

    Note:
        This service satisfies the :class:`~app.application.interfaces.IDataImporter`
        Protocol via structural subtyping.

        Layers C/D are the *tracking* layers.  Writing detection-source boxes
        (``BoxSource.DETECTION``) into layer C is technically allowed by the
        data store but semantically unusual — the dialog restricts this by
        scoping the layer combo to C/D only.

        Consider future improvement: after a successful import into layer C,
        automatically trigger ``Application.sync_tracking_cache()`` so that
        any downstream view model caches are refreshed without requiring the
        user to manually re-run tracking.
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
        Import bounding-box data from ``file_path`` into tracking ``layer``.

        Args:
            s_id:      Target session.
            layer:     Target layer — should be ``C`` or ``D`` (or their string equivalents).
            file_path: Absolute path to a ``.json`` or ``.csv`` file.
            mode:      Merge strategy (enum or string).

        Returns:
            int: Number of boxes written.

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
            raise UnsupportedLayerOperationException("tracking_import", layer)

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Import file not found: {file_path}")

        incoming = _load_file(file_path)

        session = self._app_adapter.get_session_by_id(s_id)
        total = apply_import_to_layer(session.data, layer, incoming, mode)

        logger.info(
            "TrackingImportService: imported {} box(es) into layer '{}' "
            "for session '{}' (mode={}, file='{}')",
            total, layer, s_id, mode.value, file_path,
        )
        return total


def _load_file(file_path: str) -> dict:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".json":
        return deserialize_layer_from_json(file_path)
    if ext == ".csv":
        return deserialize_layer_from_csv(file_path)
    raise UnsupportedImportExportFormatException(extension=ext, operation="tracking import")
