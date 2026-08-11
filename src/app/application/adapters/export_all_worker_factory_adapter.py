"""Infrastructure-backed factory adapter for batch export workers."""

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
    """Create concrete ``ExportAllWorker`` instances behind an interface seam."""

    def create(
        self,
        app: Application,
        s_ids: list[SessionId],
        output_dir: str,
        prefix: str,
        suffix: str,
        parent: QObject | None = None,
    ) -> ExportAllWorkerInterface:
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
