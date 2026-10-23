"""
Interface contract for creating export all worker instances.

See Also:
    - [`ExportAllWorkerFactoryAdapter`][app.application.adapters.export_all_worker_factory_adapter.ExportAllWorkerFactoryAdapter] — creates concrete batch export workers
    - [`ExportAllWorker`][app.infrastructure.export.export_all_worker.ExportAllWorker] — concrete batch worker

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
if TYPE_CHECKING:
    from app.application.interfaces.export_all.worker_interface import ExportAllWorkerInterface



if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from app.application.application import Application
    from app.domain.session import SessionId


class ExportAllWorkerFactoryInterface(Protocol):
    """
    Create start-ready export all workers behind an interface seam.

    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """

    def create(
        self,
        app: Application,
        s_ids: list[SessionId],
        output_dir: str,
        prefix: str,
        suffix: str,
        parent: QObject | None = None,
    ) -> ExportAllWorkerInterface:
        """
        Create a worker that exports several sessions sequentially.

        Args:
            app: Application facade used to access sessions and export services.
            s_ids: Session identifiers to export.
            output_dir: Directory in which exported videos are written.
            prefix: Prefix added to each generated filename.
            suffix: Suffix added to each generated filename.
            parent: Optional Qt parent that owns the worker.

        Returns:
            Batch-export worker implementing the application contract.
        """
        ...
