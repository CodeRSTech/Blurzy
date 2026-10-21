"""Infrastructure-backed factory adapter for single-session export workers.

Layer: Application.
Context: Adapts infrastructure implementations to application contracts.
"""

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
    """Create concrete `ExportWorker` instances behind an interface seam.

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
        """Create a single-session export worker behind its interface.

        Args:
            export_service: Service that renders the session export.
            s_id: Session to export.
            output_path: Destination video path.
            parent: Optional Qt parent for the worker thread.

        Returns:
            Worker adapter implementing `ExportWorkerInterface`.
        """
        from app.infrastructure.export import ExportWorker  # lazy import

        worker = ExportWorker(
            export_service=export_service,
            s_id=s_id,
            output_path=output_path,
            parent=parent,
        )
        return ExportWorkerAdapter(worker)
