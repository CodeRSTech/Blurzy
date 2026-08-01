"""Detection layer export service — serialises layers A or B to JSON / CSV."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QObject

from app.application.adapters import ApplicationAdapter
from app.application.services._layer_coercion import ensure_layer_enum
from app.application.services._layer_io import (
    serialize_layer_to_csv,
    serialize_layer_to_json,
)
from app.domain.video.layer import VideoDataLayer
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.application import Application
    from app.domain.session.session_id import SessionId

logger = get_logger("Application->DetectionExportService")

_ALLOWED_LAYERS = frozenset({VideoDataLayer.A, VideoDataLayer.B})


@final
class DetectionExportService(QObject):
    """
    Serialises detection layer data (A or B) to a file on disk.

    Responsibilities:
        - Retrieve all bounding boxes from the requested layer.
        - Write them as JSON or CSV (determined by ``file_path`` extension).
        - Return the number of boxes exported for status reporting.

    Note:
        This service satisfies the :class:`~app.application.interfaces.IDataExporter`
        Protocol via structural subtyping.

        The output file can be re-imported by :class:`DetectionImportService`
        (or even :class:`TrackingImportService`) — the wire format is layer-agnostic.

        Consider future improvement: add an optional frame-range filter
        ``(start_frame, end_frame)`` so users can export only a subset of frames,
        which is useful for long videos.
    """

    def __init__(self, app: Application) -> None:
        super().__init__(parent=app)
        self._app_adapter = ApplicationAdapter(app)

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def export_layer(
            self,
            s_id: SessionId,
            layer: VideoDataLayer | str,
            file_path: str,
    ) -> int:
        """
        Export all boxes in ``layer`` for ``s_id`` to ``file_path``.

        Args:
            s_id:      Source session.
            layer:     Source layer — should be ``A`` or ``B`` (or their string equivalents).
            file_path: Absolute destination path with ``.json`` or ``.csv`` extension.

        Returns:
            int: Number of boxes written.

        Raises:
            ValueError: If the extension is not ``.json`` or ``.csv``.

        Note:
            Accepts both ``VideoDataLayer`` enums and string layer names (``"a"``, ``"A"``, etc.)
            to handle Qt signal/slot type coercion.  Internally coerces to enum.
        """
        # ====================================================================
        # 0. COERCE LAYER TO ENUM (defensive against Qt type coercion)
        # ====================================================================
        layer = ensure_layer_enum(layer)

        if layer not in _ALLOWED_LAYERS:
            logger.warning(
                "DetectionExportService asked to read from layer '{}' — "
                "expected A or B.  Proceeding anyway.",
                layer,
            )

        # ====================================================================
        # 1. FETCH DATA
        # ====================================================================
        session = self._app_adapter.get_session_by_id(s_id)
        data = session.data.get_all_boxes_for_layer_as_dict_of_lists(layer)

        # ====================================================================
        # 2. SERIALISE
        # ====================================================================
        total = _write_file(layer.value, data, file_path)

        logger.info(
            "DetectionExportService: exported {} box(es) from layer '{}' "
            "for session '{}' to '{}'",
            total, layer, s_id, file_path,
        )
        return total


# ──────────────────────────────────────────────────────────────────────────────
#  Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _write_file(layer_name_str: str, data: dict, file_path: str) -> int:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".json":
        return serialize_layer_to_json(layer_name_str, data, file_path)
    if ext == ".csv":
        return serialize_layer_to_csv(layer_name_str, data, file_path)
    raise ValueError(
        f"Unsupported file extension '{ext}' for detection export. "
        "Expected '.json' or '.csv'."
    )
