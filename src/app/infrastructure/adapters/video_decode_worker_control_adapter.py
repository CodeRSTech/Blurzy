"""Explicit adapter wrapping ``VideoDecodeWorker`` to ``VideoDecodeWorkerControlInterface``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import VideoDecodeWorkerControlInterface

if TYPE_CHECKING:
    from app.infrastructure.dtypes import RGBFrame
    from app.infrastructure.video.decode_worker import VideoDecodeWorker


class VideoDecodeWorkerControlAdapter(VideoDecodeWorkerControlInterface):
    """
    Explicit adapter that wraps a concrete ``VideoDecodeWorker`` instance and
    exposes the ``VideoDecodeWorkerControlInterface`` contract.

    In normal usage the concrete ``VideoDecodeWorker`` already satisfies
    ``VideoDecodeWorkerControlInterface`` via structural subtyping (``Protocol``),
    so this adapter is not required for runtime correctness.  It exists to:

    - Provide an explicit, named boundary at the infrastructure/application seam.
    - Enable test doubles that replace the real worker without subclassing
      ``VideoDecodeWorker``.

    Only the control-surface methods (``set_active``, ``stop``,
    ``get_cached_frame_at_index``) are delegated; low-level ring-buffer and
    signal internals stay on the concrete worker.
    """

    def __init__(self, worker: VideoDecodeWorker) -> None:
        self._worker = worker

    def __repr__(self) -> str:
        return f"<VideoDecodeWorkerControlAdapter wrapping={self._worker!r}>"

    def set_active(self, active: bool, resume_idx: int = 0) -> None:
        self._worker.set_active(active=active, resume_idx=resume_idx)

    def stop(self) -> None:
        self._worker.stop()

    def get_cached_frame_at_index(self, idx: int) -> RGBFrame | None:
        return self._worker.get_cached_frame_at_index(idx)
