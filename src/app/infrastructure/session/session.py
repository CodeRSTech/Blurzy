"""QObject-backed session shell for per-video runtime state and layer storage.

The expensive runtime collaborators (``VideoReader``, ``SessionState`` and the
decode worker) are attached by ``SessionInitializer`` in the application layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from PySide6.QtCore import QObject

from app.domain import VideoDataLayer, SessionState
from app.shared.logging_cfg import get_logger
from app.infrastructure.session.session_data_store import SessionDataStore

if TYPE_CHECKING:
    from app.domain.session import SessionId
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict, ListOfBoxes
    from app.infrastructure.dtypes import RGBFrame
    from app.application.interfaces import DetectionEngineInterface, DetectionWorkerInterface, TrackingWorkerInterface
    from app.infrastructure.video.decode_worker import VideoDecodeWorker
    from app.infrastructure.video.vid_reader import VideoReader

logger = get_logger("Domain->Session")


@final
class Session(QObject):
    """
    Container holding the runtime state and layer storage for a single video
    processing session.

    ``Session`` stays a ``QObject`` for now, but it no longer creates its own
    video reader or decode worker. Those collaborators are attached later by
    ``SessionInitializer`` so the constructor remains side-effect free.
    """

    def __init__(self, s_id: SessionId) -> None:
        """Create a bare session shell.

        The initializer is responsible for attaching the runtime collaborators
        later. This keeps object construction predictable and easy to test.
        """
        super().__init__()

        self.s_id = s_id
        self.data = SessionDataStore(s_id=self.s_id, parent=self)
        self.video_reader: VideoReader | None = None
        self.state: SessionState | None = None
        self.video_decode_worker: VideoDecodeWorker | None = None
        self.detection_engine: DetectionEngineInterface | None = None
        self.detection_worker: DetectionWorkerInterface | None = None
        self.tracking_worker: TrackingWorkerInterface | None = None

    def __repr__(self):
        return f"<Session id={self.s_id.basename}>"

    def _require_state(self) -> SessionState:
        """Return the initialized session state or raise a clear error."""
        if self.state is None:
            raise RuntimeError(
                "Session state has not been initialized yet. "
                "Use SessionInitializer.initialize(session) before accessing playback or frame data."
            )
        return self.state

    def _require_video_reader(self) -> VideoReader:
        """Return the initialized video reader or raise a clear error."""
        if self.video_reader is None:
            raise RuntimeError(
                "Session video reader has not been initialized yet. "
                "Use SessionInitializer.initialize(session) before reading frames."
            )
        return self.video_reader

    def _require_video_decode_worker(self) -> VideoDecodeWorker:
        """Return the initialized decode worker or raise a clear error."""
        if self.video_decode_worker is None:
            raise RuntimeError(
                "Session decode worker has not been initialized yet. "
                "Use SessionInitializer.initialize(session) before reading buffered frames."
            )
        return self.video_decode_worker

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           PROPERTIES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @property
    def has_buffered_frame(self) -> bool:
        """Check if the session has a buffered frame."""
        return self.get_buffered_frame() is not None

    @property
    def has_running_detection_worker(self) -> bool:
        return self.detection_worker is not None and self.detection_worker.isRunning()

    @property
    def has_running_tracking_worker(self) -> bool:
        return self.tracking_worker is not None and self.tracking_worker.isRunning()

    @property
    def is_playing_video(self) -> bool:
        """Check if the session is currently playing the video."""
        return self._require_state().playback.is_playing

    @is_playing_video.setter
    def is_playing_video(self, is_playing: bool) -> None:
        self._require_state().playback.is_playing = is_playing

    def close(self) -> None:
        """Stop all workers (detection, tracking, decode) and close reader."""
        if self.detection_worker is not None:
            self.detection_worker.stop()
        if self.tracking_worker is not None:
            self.tracking_worker.stop()
        if self.video_decode_worker is not None:
            self.video_decode_worker.stop()

        if self.video_reader is not None:
            self.video_reader.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                            LAYER CRUD MANAGEMENT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_layer_by_name(self, layer_name: VideoDataLayer) -> ListOfBoxesByFrameIndexAsDict:
        return self.data.get_all_boxes_for_layer_as_dict_of_lists(layer_name)

    def get_layer_boxes_for_index(self, layer_name: VideoDataLayer, frame_index: int) -> ListOfBoxes:
        # Natively fetches the list directly from the Pandas dataframe!
        return self.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, frame_index)

    def get_layer_boxes_for_current_frame(self, layer_name: VideoDataLayer) -> ListOfBoxes:
        return self.get_layer_boxes_for_index(layer_name, self._require_state().playback.current_frame_index)

    def has_boxes_for_layer(self, layer_name: VideoDataLayer) -> bool:
        return self.data.has_boxes_for_layer(layer_name)

    def stop_playback(self):
        self._require_state().playback.stop_playback()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           FRAME CONTROLS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_buffered_frame(self) -> RGBFrame | None:
        """Get the next frame (current_idx + 1) from the ring buffer (for lookahead during playback)."""
        next_idx = self._require_state().playback.current_frame_index + 1
        return self.get_frame_by_index(next_idx)

    def get_frame_by_index(self, frame_index: int) -> RGBFrame | None:
        """
        Fetch frame at ``frame_index`` from the ring buffer cache with timeout-based seek handling.

        Note:
            Workflow:
                1. Clamp ``frame_index`` to the valid range.
                2. Check the ring buffer cache and return immediately on a hit.
                3. On a miss, either wait for sequential playback to catch up or trigger
                   ``request_seek()`` for a scrub jump.
                4. Wait up to 2 seconds for the worker to supply the frame.
                5. Return the frame or ``None`` on timeout.

            Side effects: updates ``playback.current_frame_index`` and
            ``current_frame_data`` when a frame is retrieved.

        Returns:
            RGBFrame | None: The requested frame, or ``None`` if it is unavailable.
        """
        import time

        session_state = self._require_state()
        max_idx = max(session_state.metadata.frame_count - 1, 0)
        safe_idx = max(0, min(frame_index, max_idx))

        decode_worker = self._require_video_decode_worker()

        # ====================================
        # 1. Check if frame at index is cached
        # ====================================
        # cached_frame = decode_worker.ring_buffer.get(safe_idx)
        # [NEW] Bypass directly accessing the ring buffer
        cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)

        if cached_frame is not None:
            # Update session state and return cached frame
            session_state.playback.current_frame_index = safe_idx
            session_state.current_frame_data = cached_frame
            return cached_frame

        # ====================================
        # 2. Cache Miss
        # ====================================
        # Check if this is a normal sequential playback (worker just fell a few ms behind)
        is_sequential_underrun = abs(safe_idx - session_state.playback.current_frame_index) <= 1

        if not is_sequential_underrun:
            # The user actually scrubbed the timeline. Force an expensive Hard Seek.
            decode_worker.request_seek(safe_idx)
        # else:
        #   It IS underrun, do nothing.
        #   Let the worker finish its sequential decoding.

        # ====================================
        # 3. Wait for worker to catch up
        # ====================================

        # TODO:
        #       Extract the timeout-loop out of `Session` and
        #       move it into the `VideoDecodeWorker` (or a new `FrameSynchronizer` class).
        #       The worker should be responsible for managing its own thread delays.
        #  OR,
        #     Use a signal-slot mechanism to notify the session when the frame is ready instead of polling.
        #  OR,
        #   Use a condition variable or event to block until the frame is available, instead of busy-waiting.
        #  OR,
        #   Pass a timeout argument `cached_frame = decode_worker.get_cached_frame_at_index(safe_idx), timeout=2.0)`
        #   and let the worker handle the waiting internally.
        attempts = 0
        while attempts < 200:  # 2.0 second timeout
            cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)
            if cached_frame is not None:
                self.state.update_current_frame_data_and_index(idx=safe_idx, frame_data=cached_frame)
                return cached_frame
            time.sleep(0.01)
            attempts += 1

        logger.error("Timeout waiting for worker to supply frame {}", safe_idx)
        return None

    def get_current_frame(self) -> RGBFrame | None:
        """Get frame at current playback position (caches result in state)."""
        session_state = self._require_state()
        current_index = session_state.playback.current_frame_index

        # FIX: Ensure we actually update and return the fallback data if empty!
        if session_state.current_frame_data is None:
            session_state.current_frame_data = self.get_frame_by_index(current_index)

        return session_state.current_frame_data

    def get_next_frame(self) -> RGBFrame | None:
        """Get next frame (current_idx + 1)."""
        return self.get_frame_by_index(self._require_state().playback.current_frame_index + 1)

    def get_previous_frame(self) -> RGBFrame | None:
        """Get previous frame (current_idx - 1)."""
        return self.get_frame_by_index(self._require_state().playback.current_frame_index - 1)

    def reset_model(self, model_name: str, keep_manual: bool = False) -> None:
        """
        Change the detection model and clear Layers B and D.

        Note:
            If ``model_name == "None"``, all layers (A, B, C, and D) are cleared.
            Otherwise the new model name is stored and Layers B and D are cleared while
            optionally preserving manual annotations.
        """

        if model_name == "None":
            logger.info("Deleting detection engine and session layers for Session: '{}'", self.s_id)
            self.data.clear_all_layers(keep_manual=keep_manual)
            return

        self._require_state().settings.detection_model_name = model_name
        self.data.clear_layer_by_name(VideoDataLayer.B, keep_manual)
        self.data.clear_layer_by_name(VideoDataLayer.D, keep_manual)

        logger.info("Detection model set for session '{}'. Layers cleared.", self.s_id)
