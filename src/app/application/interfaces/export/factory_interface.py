"""Interface contract for creating export worker instances.

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
if TYPE_CHECKING:
    from app.application.interfaces.export.worker_interface import ExportWorkerInterface




if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from app.application.services.export_service import ExportService
    from app.domain.session import SessionId


class ExportWorkerFactoryInterface(Protocol):
    """Create start-ready export workers behind an interface seam.

Layer: Application.
Context: Coordinates use-case behavior through domain services and application contracts.
"""

    def create(
        self,
        export_service: ExportService,
        s_id: SessionId,
        output_path: str,
        parent: QObject | None = None,
    ) -> ExportWorkerInterface:
        """Create a worker that exports one session to a video file.

        Args:
            export_service: Service that renders the session's frames and annotations.
            s_id: Identifier of the session to export.
            output_path: Destination path for the exported video.
            parent: Optional Qt parent that owns the worker.

        Returns:
            Export worker implementing the application contract.
        """
        ...
