"""Interface contract for creating export all worker instances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.application.interfaces.export_all.worker_interface import ExportAllWorkerInterface

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from app.application.application import Application
    from app.domain.session import SessionId


class ExportAllWorkerFactoryInterface(Protocol):
    """Create start-ready export all workers behind an interface seam."""

    def create(
        self,
        app: Application,
        s_ids: list[SessionId],
        output_dir: str,
        prefix: str,
        suffix: str,
        parent: QObject | None = None,
    ) -> ExportAllWorkerInterface:
        """Build and return an export all worker instance."""
        ...
