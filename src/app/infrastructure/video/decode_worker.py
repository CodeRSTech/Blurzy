"""Background video decoding worker with ring buffer cache and hard-seek support."""

import time
from typing import final

from PySide6.QtCore import QMutex, QMutexLocker, QThread, QObject, Signal

from app.infrastructure.dtypes import RGBFrame
from app.domain.video.playback_state import PlaybackState
from app.domain.video.ring_buffer import VideoRingBuffer
from app.infrastructure.video.vid_reader import VideoReader
from app.shared.logging_cfg import get_logger

logger = get_logger("Infrastructure->VideoDecodeWorker")


class DecoderSignals(QObject):
    """Container for Qt signals emitted by ``VideoDecodeWorker`` (must inherit ``QObject``)."""
    # Signals must be defined on a QObject.
    # Emits (frame_index) when a sought frame is successfully cached
    seek_completed = Signal(int)


@final
class VideoDecodeWorker(QThread):
    """Background worker that decodes video frames into a ring buffer.

    This thread preloads frames ahead of playback, handles seek requests,
    and manages memory usage by clearing cached frames when inactive.

    Attributes:
        signals (DecoderSignals): Signal container emitting seek completion events.
        ring_buffer (VideoRingBuffer): Frame cache (90-frame sliding window).
        _reader (VideoReader): Video reader used to decode frames.
        _playback (PlaybackState): Shared playback state reference.
        _is_active (bool): True when the worker should decode/cache frames.
        _running (bool): True while the run loop is active.
        _seek_request (int | None): Pending seek target frame index.
        _latest_read_idx (int): Most recent frame index pushed to the buffer.
        _mutex (QMutex): Guards mutable cross-thread state.

    Notes:
        Core loop behavior:
            1. If inactive, sleep briefly.
            2. If a seek is requested, perform a hard seek and emit completion.
            3. If the buffer is sufficiently ahead, throttle decode rate.
            4. Otherwise decode the next frame and push to the ring buffer.

        Memory behavior:
            - Buffer capacity is 90 frames.
            - Buffer is cleared on seek and when deactivated.
            - Deactivation is used to aggressively release cached frame memory.

        Thread lifecycle (caller responsibility):
            Call in this order: ``stop()`` -> ``quit()`` -> ``wait()`` -> ``deleteLater()``.

    Example:
        UI seek flow:
            `slider moved` -> ``set_active(False)``, ``request_seek(idx)``

            run loop handles seek and caches frame

            ``signals.seek_completed(idx)`` emitted

            UI resumes decode with ``set_active(True)``
    """
    def __init__(
            self, path: str, playback: PlaybackState, parent=None
    ) -> None:
        """Initialize decode worker for ``path`` with reference to ``playback`` state."""
        super().__init__(parent)  # Important for garbage collection
        self.signals = DecoderSignals()
        self._running = False
        self._is_active = False
        self._reader: VideoReader = VideoReader(path)
        self._playback: PlaybackState = playback

        # The new High-Performance Sliding Window Cache
        # [AUDIT] CONFIGURATION: Hard-coded capacity (90 frames) not configurable
        # 90 frames may be insufficient for high-FPS videos (e.g., 60 FPS = 1.5 seconds)
        # or excessive for low-FPS videos (e.g., 2 FPS = 45 seconds of memory overhead).
        # Recommendation: Make capacity configurable via:
        #   - RuntimeConfig or settings
        #   - Constructor parameter with intelligent default (e.g., 90 or FPS-dependent)
        # Current fixed capacity: 90 frames (suitable for ~30 FPS @ 3 second lookahead)
        self.ring_buffer = VideoRingBuffer(capacity=90)
        self._latest_read_idx = -1

        # Thread-safe seeking state
        self._seek_request: int | None = None
        self._mutex = QMutex()  # Upgraded to Qt Mutex

        logger.debug(
            "Decode worker initialized for video reader with '{}', parent={}",
            self._reader.path_file_name,
            parent,
        )

    def request_seek(self, frame_index: int) -> None:
        """Request hard seek to ``frame_index`` (thread-safe, clears buffer)."""
        with QMutexLocker(self._mutex):
            self._seek_request = frame_index
            self.ring_buffer.clear()

    def run(self) -> None:
        """
        Main QThread loop — decode frames ahead of playback, handle seeks, manage buffer.

        **Workflow:**

        - Check if active; if not, sleep 10ms
        - Handle pending seek request (hard seek via ``VideoReader``, emit ``seek_completed``)
        - Throttle if buffer ahead by 45 frames (sleep 10ms)
        - Read next frame sequentially, push to ring buffer
        - Repeat until ``_running`` becomes False
        """
        self._running = True
        logger.debug(
            "Starting QThread decode worker for video {}", self._reader.basename
        )

        while self._running:
            # 0. Check if the worker is active
            if not self._is_active:
                time.sleep(0.01)
                continue

            # 1. Handle Hard Seeks
            with QMutexLocker(self._mutex):
                target_seek = self._seek_request
                self._seek_request = None

            if target_seek is not None:
                logger.trace("Executing Hard Seek to frame {}...", target_seek)
                self.ring_buffer.clear()
                try:
                    frame = self._reader.read_frame_at_index(target_seek)
                    if frame is not None:
                        self.ring_buffer.push(target_seek, frame)
                        self._latest_read_idx = target_seek

                        # --- THE MAGIC BULLET ---
                        # Tap the UI on the shoulder to tell it the seek is done!
                        self.signals.seek_completed.emit(target_seek)

                except Exception as e:
                    logger.error(f"Error during seek to {target_seek}: {e}")
                continue

            # 2. Throttling (Buffer is full)
            ui_idx = self._playback.current_frame_index
            if self._latest_read_idx >= ui_idx + 45:
                time.sleep(0.01)
                continue

            # 3. Sequential Reading (Fast Path)
            try:
                idx, frame = self._reader.read_next_frame()
                self.ring_buffer.push(idx, frame)
                self._latest_read_idx = idx
            except ValueError:
                time.sleep(0.1)  # End of video
            except Exception as e:
                logger.error(
                    f"Error sequentially reading frame {self._latest_read_idx}: {e}"
                )

    def set_active(self, active: bool, resume_idx: int = 0) -> None:
        """
        Toggle worker on/off (thread-safe via ``_mutex``).

        **When False:** Clears ring buffer (frees ~2.2GB RAM immediately).
        **When True:** Schedules seek to ``resume_idx`` to refill buffer from playhead.
        """
        with QMutexLocker(self._mutex):
            self._is_active = active
            if not active:
                self.ring_buffer.clear()  # Dump the 2.2GB of RAM immediately
            else:
                self._seek_request = resume_idx  # Force a refill from the playhead

    def stop(self) -> None:
        """
        Safely shutdown QThread with proper cleanup sequence.

        **Sequence:**

        1. Set ``_running=False`` (exit main loop)
        2. Call ``quit()`` (signal quit)
        3. Call ``wait(500)`` (up to 500ms for loop exit)
        4. If stuck, ``terminate()`` then ``wait()`` (fallback for deadlock)
        5. Close ``VideoReader``

        [IMPORTANT] Always call this before thread deletion to avoid zombie threads.
        """
        logger.debug("Stopping decode worker for video {}", self._reader.basename)
        self._running = False
        self.quit()
        # Wait up to 500ms for the while loop to exit cleanly
        if not self.wait(500):
            self.terminate()  # Absolute last resort if stuck in C-level deadlock
            self.wait()
        self._reader.close()

    def get_cached_frame_at_index(self, idx: int) -> RGBFrame | None:
        """Return cached frame at ``idx``, or None if not in buffer."""
        return self.ring_buffer.get(idx)
