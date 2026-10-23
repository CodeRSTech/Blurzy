"""
Frame retrieval orchestration for session decode workers.

This module isolates cache lookup + seek + timeout polling from `Session` so
the QObject container remains focused on view_state ownership.

See Also:
    - [`VideoRingBuffer`][app.domain.video.ring_buffer.VideoRingBuffer] — provides cached frame lookup
    - [`Session`][app.infrastructure.session.session.Session] — delegates frame retrieval to this accessor


Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
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
    """
    Resolve requested frames through the decode worker cache.

    The accessor preserves the existing playback semantics:
      1. Clamp frame index to valid metadata range.
      2. Return cache hits immediately.
      3. Trigger `request_seek` for non-sequential jumps.
      4. Poll for worker output until timeout.
      5. Synchronize session view_state on successful retrieval.


    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        timeout_seconds: Maximum time to wait for a decoded frame.
        poll_interval_seconds: Delay between checks for a decoded frame.
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
        """
        Return a clamped frame index from cache, seeking and polling on a cache miss.

        Args:
            session_state: Session state providing frame-count bounds and playback cache.
            decode_worker: Decode worker that owns the ring buffer cache.
            frame_index: Requested index; it is clamped to the available metadata range.

        Returns:
            Decoded RGB frame, or `None` if it is not available before the timeout.

        Side Effects:
            On a cache hit or successful poll, updates the current frame index and
            frame-data cache. A seek is requested for non-sequential misses and
            misses of the current frame.
        """
        max_idx = max(session_state.metadata.frame_count - 1, 0)
        safe_idx = max(0, min(frame_index, max_idx))

        cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)
        if cached_frame is not None:
            session_state.playback.current_frame_index = safe_idx
            session_state.current_frame_data = cached_frame
            return cached_frame

        is_sequential_underrun = abs(safe_idx - session_state.playback.current_frame_index) <= 1
        is_current_frame_cache_miss = (
            safe_idx == session_state.playback.current_frame_index
            and session_state.current_frame_data is None
        )
        should_request_seek = (not is_sequential_underrun) or is_current_frame_cache_miss
        if should_request_seek:
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

    def get_current_frame(
        self,
        *,
        session_state: SessionState,
        decode_worker: VideoDecodeWorker,
    ) -> RGBFrame | None:
        """
        Return the cached frame at the current playback position, loading it if absent.

        Args:
            session_state: Session playback state and current-frame cache.
            decode_worker: Worker providing decoded frames.

        Returns:
            Current RGB frame, or `None` if retrieval times out.

        Side Effects:
            On a cache miss, delegates to `get_frame_by_index`, which may seek,
            wait for decoding, and update session playback/cache state.
        """
        if session_state.current_frame_data is None:
            current_index = session_state.playback.current_frame_index
            session_state.current_frame_data = self.get_frame_by_index(
                session_state=session_state,
                decode_worker=decode_worker,
                frame_index=current_index,
            )
        return session_state.current_frame_data

    def get_next_frame(
        self,
        *,
        session_state: SessionState,
        decode_worker: VideoDecodeWorker,
    ) -> RGBFrame | None:
        """
        Request the frame one index after the current playback position.

        Args:
            session_state: Playback state whose index and frame cache are updated.
            decode_worker: Worker providing decoded frames and seek requests.

        Returns:
            Next RGB frame, or `None` if it is not decoded before the timeout.

        Side Effects:
            The requested index is clamped to the metadata range, so the final
            frame is returned again when playback is already at the end. On
            success, updates the playback index and current-frame cache.
        """
        return self.get_frame_by_index(
            session_state=session_state,
            decode_worker=decode_worker,
            frame_index=session_state.playback.current_frame_index + 1,
        )

    def get_previous_frame(
        self,
        *,
        session_state: SessionState,
        decode_worker: VideoDecodeWorker,
    ) -> RGBFrame | None:
        """
        Request the frame one index before the current playback position.

        Args:
            session_state: Playback state whose index and frame cache are updated.
            decode_worker: Worker providing decoded frames and seek requests.

        Returns:
            Previous RGB frame, or `None` if it is not decoded before the timeout.

        Side Effects:
            The requested index is clamped to the metadata range, so frame zero
            is returned again when playback is already at the beginning. On
            success, updates the playback index and current-frame cache.
        """
        return self.get_frame_by_index(
            session_state=session_state,
            decode_worker=decode_worker,
            frame_index=session_state.playback.current_frame_index - 1,
        )

    def get_buffered_frame(
        self,
        *,
        session_state: SessionState,
        decode_worker: VideoDecodeWorker,
    ) -> RGBFrame | None:
        """
        Return lookahead frame (current index + 1) from decode cache flow.

        Args:
            session_state: Playback state whose index and frame cache are updated.
            decode_worker: Worker providing decoded frames and seek requests.

        Returns:
            Next RGB frame, or `None` if it is not decoded before the timeout.

        Side Effects:
            Because this delegates to `get_next_frame`, successful retrieval
            also advances the playback index and updates the current-frame cache.
        """
        return self.get_next_frame(session_state=session_state, decode_worker=decode_worker)
