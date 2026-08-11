"""Infrastructure-backed factory adapter for single-session export workers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import ExportWorkerFactoryInterface
from app.infrastructure.adapters.export_worker_adapter import ExportWorkerAdapter
if TYPE_CHECKING:
    from app.application.interfaces import ExportWorkerInterface


if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from app.application.services.export_service import ExportService
    from app.domain.session import SessionId


class ExportWorkerFactoryAdapter(ExportWorkerFactoryInterface):
    """Create concrete ``ExportWorker`` instances behind an interface seam."""

    def create(
        self,
        export_service: ExportService,
        s_id: SessionId,
        output_path: str,
        parent: QObject | None = None,
    ) -> ExportWorkerInterface:
        from app.infrastructure.export import ExportWorker  # lazy import

        worker = ExportWorker(
            export_service=export_service,
            s_id=s_id,
            output_path=output_path,
            parent=parent,
        )
        return ExportWorkerAdapter(worker)
