"""Interface contract for controlling the video decode worker (activate/deactivate)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.infrastructure.dtypes import RGBFrame


class VideoDecodeWorkerControlInterface(Protocol):
    """
    Abstraction boundary for the video decode worker's activation controls.

    Allows callers (e.g. ``VideoDecodeWorkerManager``) to activate, deactivate,
    and stop the worker, and to read cached frames — without depending on the
    concrete ``VideoDecodeWorker`` class.
    """

    def set_active(self, active: bool, resume_idx: int = 0) -> None:
        """
        Toggle the worker on (``True``) or off (``False``).

        When activated, the worker seeks to ``resume_idx`` and begins buffering
        frames from that position.  When deactivated, the ring buffer is cleared
        to release memory immediately.
        """
        ...

    def stop(self) -> None:
        """Shut down the worker thread cleanly."""
        ...

    def get_cached_frame_at_index(self, idx: int) -> RGBFrame | None:
        """Return the cached frame at ``idx``, or ``None`` if not in the buffer."""
        ...
