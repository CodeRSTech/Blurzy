"""Infrastructure-backed factory adapter for batch export workers.

See Also:
    - [`ExportAllWorkerFactoryInterface`][app.application.interfaces.export_all.worker_factory_interface.ExportAllWorkerFactoryInterface] — defines the factory contract
    - [`ExportAllWorkerAdapter`][app.infrastructure.adapters.export_all_worker_adapter.ExportAllWorkerAdapter] — adapts the concrete worker to its interface

Layer: Application.
Context: Adapts infrastructure implementations to application contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import ExportAllWorkerFactoryInterface
from app.infrastructure.adapters.export_all_worker_adapter import ExportAllWorkerAdapter
if TYPE_CHECKING:
    from app.application.interfaces import ExportAllWorkerInterface


if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from app.application.application import Application
    from app.domain.session import SessionId


class ExportAllWorkerFactoryAdapter(ExportAllWorkerFactoryInterface):
    """Create concrete `ExportAllWorker` instances behind an interface seam.

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
        """Create a batch export worker behind its interface.

        Args:
            app: Application that owns the sessions and export services.
            s_ids: Sessions to export in sequence.
            output_dir: Directory receiving the exported videos.
            prefix: Prefix added to each output filename.
            suffix: Suffix added to each output filename.
            parent: Optional Qt parent for the worker thread.

        Returns:
            Worker adapter implementing `ExportAllWorkerInterface`.
        """
        from app.infrastructure.export import ExportAllWorker  # lazy import

        worker = ExportAllWorker(
            app=app,
            s_ids=s_ids,
            output_dir=output_dir,
            prefix=prefix,
            suffix=suffix,
            parent=parent,
        )
        return ExportAllWorkerAdapter(worker)
