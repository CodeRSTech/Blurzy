"""Interface contract for creating export worker instances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.application.interfaces.export.worker_interface import ExportWorkerInterface

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from app.application.services.export_service import ExportService
    from app.domain.session import SessionId


class ExportWorkerFactoryInterface(Protocol):
    """Create start-ready export workers behind an interface seam."""

    def create(
        self,
        export_service: ExportService,
        s_id: SessionId,
        output_path: str,
        parent: QObject | None = None,
    ) -> ExportWorkerInterface:
        """Build and return an export worker instance."""
        ...
