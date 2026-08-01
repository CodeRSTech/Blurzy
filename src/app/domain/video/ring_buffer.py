"""Circular frame buffer with thread-safe O(1) lookup for video playback buffering."""

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.dtypes import RGBFrame


class VideoRingBuffer:
    """
    High-performance circular array (ring buffer) for caching contiguous frame sequences.

    Attributes:
        capacity (int): Fixed number of frames cached in the ring.

    Note:
        Provides O(1) frame lookup through modulo hashing while tracking a
        contiguous ``[start_idx, end_idx]`` range. Uses a lightweight
        ``threading.Lock()`` for thread safety and pre-allocates storage with
        no dynamic resizing. Used by ``VideoDecodeWorker`` for both sequential
        playback buffering and hard seeks. When the buffer wraps, the oldest
        frame is overwritten and the start index advances.

    Example:
        buffer = VideoRingBuffer(capacity=90)
        buffer.push(0, frame_0)
        buffer.push(1, frame_1)
        frame = buffer.get(0)  # O(1) lookup
        buffer.clear()  # Free memory for inactive session
    """

    def __init__(self, capacity: int = 90):
        """Initialize ring buffer with ``capacity`` pre-allocated slots."""
        self.capacity = capacity
        # Pre-allocate physical memory slots
        self._frames: list[RGBFrame | None] = [None] * capacity

        # Track the contiguous bounds of the buffer
        self._start_idx = -1
        self._end_idx = -1

        self._lock = threading.Lock()

    def push(self, idx: int, frame: RGBFrame) -> None:
        """
        Push ``frame`` at ``idx`` (thread-safe), update bounds, handle wrapping.

        Args:
            idx (int): Frame index to store.
            frame (RGBFrame): Decoded RGB frame data to cache.

        Note:
            If the buffer is empty or a hard seek introduces a gap in the
            sequence, the start index resets to ``idx``. The frame is stored in
            slot ``idx % capacity``, the end index is updated, and wrapping
            advances the start index when the oldest frame is overwritten.
        """
        with self._lock:
            # If the queue is empty, or the worker skipped frames (Hard Seek), reset bounds
            if self._start_idx == -1 or idx != self._end_idx + 1:
                self._start_idx = idx

            self._end_idx = idx

            # Modulo math to find the physical memory slot
            slot = idx % self.capacity
            self._frames[slot] = frame

            # If the worker has wrapped entirely around the ring, the tail eats the head
            if self._end_idx - self._start_idx >= self.capacity:
                self._start_idx = self._end_idx - self.capacity + 1

    def get(self, idx: int) -> RGBFrame | None:
        """Return cached frame at ``idx``, or None if cache miss (out of bounds)."""
        with self._lock:
            if self._start_idx <= idx <= self._end_idx:
                slot = idx % self.capacity
                return self._frames[slot]
            return None

    def clear(self) -> None:
        """Reset buffer bounds and clear all slots (frees memory for inactive sessions)."""
        with self._lock:
            self._start_idx = -1
            self._end_idx = -1

            # NEW! Reset the frames list to clear the buffer and free memory
            self._frames = [None] * self.capacity
