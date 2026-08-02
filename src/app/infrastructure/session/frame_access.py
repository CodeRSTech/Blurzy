"""Frame retrieval orchestration for session decode workers.

This module isolates cache lookup + seek + timeout polling from ``Session`` so
the QObject container remains focused on state ownership.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, final

from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.session import SessionState
    from app.infrastructure.dtypes import RGBFrame
    from app.infrastructure.video.decode_worker import VideoDecodeWorker

logger = get_logger("Infrastructure->SessionFrameAccessor")


@final
class SessionFrameAccessor:
    """Resolve requested frames through the decode worker cache.

    The accessor preserves the existing playback semantics:
      1. Clamp frame index to valid metadata range.
      2. Return cache hits immediately.
      3. Trigger ``request_seek`` for non-sequential jumps.
      4. Poll for worker output until timeout.
      5. Synchronize session state on successful retrieval.
    """

    def __init__(self, timeout_seconds: float = 2.0, poll_interval_seconds: float = 0.01) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")

        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    def get_frame_by_index(
        self,
        *,
        session_state: SessionState,
        decode_worker: VideoDecodeWorker,
        frame_index: int,
    ) -> RGBFrame | None:
        """Return the requested frame from cache or ``None`` on timeout.

        Args:
            session_state: Runtime state for playback index and metadata bounds.
            decode_worker: Decode worker that owns the ring buffer cache.
            frame_index: Raw target index requested by the caller.
        """
        max_idx = max(session_state.metadata.frame_count - 1, 0)
        safe_idx = max(0, min(frame_index, max_idx))

        cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)
        if cached_frame is not None:
            session_state.playback.current_frame_index = safe_idx
            session_state.current_frame_data = cached_frame
            return cached_frame

        is_sequential_underrun = abs(safe_idx - session_state.playback.current_frame_index) <= 1
        if not is_sequential_underrun:
            decode_worker.request_seek(safe_idx)

        max_attempts = max(1, int(self._timeout_seconds / self._poll_interval_seconds))
        for _ in range(max_attempts):
            cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)
            if cached_frame is not None:
                session_state.update_current_frame_data_and_index(idx=safe_idx, frame_data=cached_frame)
                return cached_frame
            time.sleep(self._poll_interval_seconds)

        logger.error("Timeout waiting for worker to supply frame {}", safe_idx)
        return None

