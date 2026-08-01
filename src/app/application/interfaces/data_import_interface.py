"""Protocol interface for layer data importers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.video.layer import VideoDataLayer
    from app.domain.session.session_id import SessionId
    from app.application.services.import_mode import ImportMode


@runtime_checkable
class IDataImporter(Protocol):
    """
    Abstraction boundary for services that load bounding-box data from a file
    into a session layer.

    Any object that exposes ``import_layer()`` with a matching signature satisfies
    this interface — no explicit inheritance is required (structural subtyping via
    ``Protocol``).

    Note:
        Two concrete implementations exist:

        * ``DetectionImportService`` — targets detection layers (A / B).
        * ``TrackingImportService``  — targets tracking  layers (C / D).

        Both share the same wire-format logic from
        :mod:`app.application.services._layer_io` so the file produced by one
        can be read back by the other (cross-layer import is intentionally
        supported by the dialog).

        Consider future improvement: add a ``validate_file(file_path) -> bool``
        method to the interface so callers can dry-run schema validation before
        committing to the import.
    """

    def import_layer(
        self,
        s_id: SessionId,
        layer: VideoDataLayer,
        file_path: str,
        mode: ImportMode | str,
    ) -> int:
        """
        Import bounding-box data from ``file_path`` into ``layer`` for ``s_id``.

        Args:
            s_id:      Target session.
            layer:     Target layer inside the session's ``SessionDataStore``.
            file_path: Absolute path to a ``.json`` or ``.csv`` file produced by
                       :class:`IDataExporter`.
            mode:      Merge strategy — accepts enum or string and is coerced
                       to :class:`~app.application.services.import_mode.ImportMode`.

        Returns:
            int: Number of boxes actually written into the layer.
        """
        ...

