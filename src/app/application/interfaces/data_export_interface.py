"""Protocol interface for layer data exporters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.video.layer import VideoDataLayer
    from app.domain.session.session_id import SessionId


@runtime_checkable
class IDataExporter(Protocol):
    """
    Abstraction boundary for services that serialise a session layer to a file.

    Any object that exposes ``export_layer()`` with a matching signature satisfies
    this interface — no explicit inheritance required (structural subtyping via
    ``Protocol``).

    Note:
        Two concrete implementations exist:

        * ``DetectionExportService`` — reads from detection layers (A / B).
        * ``TrackingExportService``  — reads from tracking  layers (C / D).

        The file format (JSON or CSV) is determined by the extension of
        ``file_path`` and handled entirely by the concrete service; callers
        do not need to be aware of the format.

        Consider future improvement: add a ``supported_formats() -> list[str]``
        method to the interface so the dialog can dynamically build its format
        combo box from what the service advertises, rather than hard-coding
        ``["json", "csv"]`` on the UI side.
    """

    def export_layer(
        self,
        s_id: SessionId,
        layer: VideoDataLayer,
        file_path: str,
    ) -> int:
        """
        Export bounding-box data from ``layer`` for session ``s_id`` to ``file_path``.

        Args:
            s_id:      Source session.
            layer:     Source layer inside the session's ``SessionDataStore``.
            file_path: Absolute destination path.  The file extension (``.json``
                       or ``.csv``) determines the serialisation format.

        Returns:
            int: Number of boxes written to the file.

        Raises:
            ValueError: If the file extension is not recognised.
        """
        ...

