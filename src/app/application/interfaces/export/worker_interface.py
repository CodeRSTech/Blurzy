"""Interface contract for background single-session export worker implementations."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import SignalInstance


class ExportWorkerInterface(Protocol):
    """Abstraction boundary for single-session export workers."""

    progress_updated = SignalInstance
    succeeded = SignalInstance
    finished_processing = SignalInstance
    cancelled = SignalInstance
    error_occurred = SignalInstance

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

    def wait(self) -> None:
        """Wait for the export thread to finish."""
        ...
    