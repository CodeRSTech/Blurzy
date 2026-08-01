"""Interface contract for background batch export worker implementations."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import SignalInstance


class ExportAllWorkerInterface(Protocol):
    """Abstraction boundary for batch export workers."""

    session_started = SignalInstance
    session_finished = SignalInstance
    session_failed = SignalInstance
    progress_updated = SignalInstance
    session_export_progress_updated = SignalInstance
    finished_processing = SignalInstance
    cancelled = SignalInstance

    def start(self) -> None:
        """Start the export thread."""
        ...

    def stop(self) -> None:
        """Request the export thread to stop."""
        ...

    def isRunning(self) -> bool:
        """Return ``True`` while the worker thread is active."""
        ...

    def deleteLater(self) -> None:
        """Schedule worker object deletion on the Qt event loop."""
        ...
